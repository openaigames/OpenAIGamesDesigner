#!/usr/bin/env python3
"""Portable local Moodboard editor and versioned Art Direction export (stdlib only)."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import struct
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4
import zlib

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "moodboard-editor"
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\Z")
HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
MAX_BODY = 80 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def contained(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("需要以 / 分隔的相对路径")
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("路径必须位于指定项目或图板内")
    return path


def image_type(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise ValueError("仅支持 PNG、JPEG、WebP 原图；请先转换其他格式")


def png_check(data):
    """Check the browser's flattened PNG integrity; this is not visual approval."""
    if image_type(data) != "png":
        raise ValueError("需要完整 PNG 图板")
    offset, packed, header, ended = 8, bytearray(), None, False
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        tag = data[offset + 4:offset + 8]
        body = data[offset + 8:offset + 8 + size]
        tail = data[offset + 8 + size:offset + 12 + size]
        if len(tail) != 4 or zlib.crc32(tag + body) & 0xffffffff != int.from_bytes(tail, "big"):
            raise ValueError("PNG 数据不完整")
        offset += size + 12
        if tag == b"IHDR":
            if header is not None or size != 13:
                raise ValueError("PNG 头无效")
            header = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            packed.extend(body)
        elif tag == b"IEND":
            ended = size == 0 and offset == len(data)
            break
    if not header or not ended:
        raise ValueError("PNG 缺少完整图像数据")
    w, h, depth, color, compression, filtering, interlace = header
    if w != 2000 or not 400 <= h <= 16000 or depth != 8 or color not in (2, 6) or any((compression, filtering, interlace)):
        raise ValueError("PNG 尺寸或编码不符合编辑器输出")
    expected = (w * (4 if color == 6 else 3) + 1) * h
    decoder = zlib.decompressobj()
    raw = decoder.decompress(packed, expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError("PNG 像素数据不完整")
    return {"width": w, "height": h, "sha256": digest(data)}


def validate(board, folder=None, allow_data=False):
    if not isinstance(board, dict) or board.get("schemaVersion") != 2:
        raise ValueError("需要 schemaVersion: 2 的图板配置；旧验证样例须显式迁移")
    if not ID.fullmatch(board.get("id", "")) or board.get("scope") not in ("game-theme", "asset"):
        raise ValueError("图板标识或范围无效")
    if type(board.get("revision")) is not int or board["revision"] < 0:
        raise ValueError("版本无效")
    if board.get("scope") == "asset" and not isinstance(board.get("assetId"), str):
        raise ValueError("资产板需要 assetId（可填写项目已有资产标识）")
    for key in ("title", "intent", "selectionBasis"):
        if not isinstance(board.get(key), str) or len(board[key]) > (200 if key == "title" else 2000):
            raise ValueError("标题、意图或选用依据无效")
    if not board["title"].strip() or "\n" in board["title"] or "\r" in board["title"]:
        raise ValueError("标题需要单行非空文字")
    if board.get("status") not in ("candidate", "selected", "deferred"):
        raise ValueError("选用状态无效")
    if board["status"] == "selected" and not board["selectionBasis"].strip():
        raise ValueError("选用方向需记录已有选择或委托依据")
    direction = board.get("direction")
    if not isinstance(direction, dict) or any(not isinstance(v, str) or len(v) > 2000 for v in direction.values()):
        raise ValueError("方向摘要须使用简短文本字段")
    parent = board.get("parent")
    if parent is not None:
        if not isinstance(parent, dict) or not ID.fullmatch(parent.get("id", "")) or parent["id"] == board["id"]:
            raise ValueError("主题关联无效")
        if type(parent.get("revision")) is not int or parent["revision"] < 0:
            raise ValueError("主题关联需要明确版本")
    for key, minimum, maximum in (("palette", 1, 12), ("references", 0, 40)):
        entries = board.get(key)
        if not isinstance(entries, list) or not minimum <= len(entries) <= maximum:
            raise ValueError(f"{key} 数量超出工具容量")
        seen = set()
        for item in entries:
            if not isinstance(item, dict) or not ID.fullmatch(item.get("id", "")) or item["id"] in seen:
                raise ValueError(f"{key} 标识无效或重复")
            seen.add(item["id"])
            if key == "palette":
                if not HEX.fullmatch(item.get("hex", "")) or not isinstance(item.get("name"), str) or len(item["name"]) > 80:
                    raise ValueError("色槽需要名称与 #RRGGBB")
            else:
                for field in ("title", "note", "exclude", "sourceLabel", "sourceUrl", "usage"):
                    if not isinstance(item.get(field), str) or len(item[field]) > 2000:
                        raise ValueError("参考图说明字段缺失或过长")
                if item.get("role") not in ("primary", "supporting") or type(item.get("viewed")) is not bool:
                    raise ValueError("参考职责或查看状态无效")
                if item["sourceUrl"] and urlsplit(item["sourceUrl"]).scheme not in ("http", "https"):
                    raise ValueError("来源链接须为 http/https")
                if "data" in item:
                    if not allow_data:
                        raise ValueError("暂存上传数据需要先通过编辑器保存")
                    decode_image(item["data"])
                elif folder is not None:
                    file = contained(folder, item.get("file"))
                    if not file.is_file():
                        raise ValueError("参考文件不存在：" + item["id"])
                    raw = file.read_bytes()
                    image_type(raw)
                    if item.get("sha256") and digest(raw) != item["sha256"]:
                        raise ValueError("原图与保存版本校验值不同：" + item["id"] + "；请作为替换图片处理")
                elif not isinstance(item.get("file"), str):
                    raise ValueError("参考图缺少 file")
    return board


def decode_image(value):
    if not isinstance(value, str) or not re.match(r"^data:image/(png|jpeg|webp);base64,", value):
        raise ValueError("图片数据格式无效")
    data = base64.b64decode(value.partition(",")[2], validate=True)
    if not 0 < len(data) <= 20 * 1024 * 1024:
        raise ValueError("单张原图须不超过 20 MB")
    image_type(data)
    return data


def keep_image(folder, data):
    target = contained(folder, "images/" + digest(data) + "." + image_type(data))
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(data)
    elif target.read_bytes() != data:
        raise ValueError("已保存原图与校验值不一致")
    return target.relative_to(folder).as_posix()


def write_bootstrap(folder, board):
    # Escaping '<' also makes this safe if a host later embeds the JSON in HTML.
    portable = json.loads(json.dumps(board))
    for ref in portable["references"]:
        data = contained(folder, ref["file"]).read_bytes()
        mime = {"png": "png", "jpg": "jpeg", "webp": "webp"}[image_type(data)]
        ref["data"] = "data:image/" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    value = json.dumps(portable, ensure_ascii=False).replace("<", "\\u003c")
    atomic(folder / "board-data.js", ("window.MOODBOARD_DATA=" + value + ";\n").encode())


class ProjectBoard:
    def __init__(self, project, board_dir, document="Art Direction.md"):
        self.project = Path(project).resolve()
        self.folder = contained(self.project, board_dir)
        self.document = contained(self.project, document)
        if self.document.suffix.lower() != ".md" or self.document.is_relative_to(self.folder):
            raise ValueError("Art Direction 应是图板目录外的项目 Markdown 文件")
        self.current = self.folder / "board.json"

    def read(self):
        raw = self.current.read_bytes()
        return validate(json.loads(raw), self.folder), digest(raw)

    def warnings(self, board):
        warnings = []
        parent = board.get("parent")
        for path in self.folder.parent.glob("*/board.json"):
            if path.resolve() == self.current.resolve():
                continue
            try:
                other = json.loads(path.read_bytes())
                if parent and other["id"] == parent["id"] and other["revision"] != parent["revision"]:
                    warnings.append(f"主题 {parent['id']} 已到 v{other['revision']}；本板仍引用 v{parent['revision']}，需复核继承关系。")
                relation = other.get("parent") or {}
                if relation.get("id") == board["id"] and relation.get("revision") != board["revision"]:
                    warnings.append(f"资产板 {other['id']} 仍引用旧主题版本，需复核；未自动改动。")
            except (ValueError, KeyError, TypeError, OSError):
                continue
        for receipt in (self.folder / "versions").glob("*/receipt.json"):
            if json.loads(receipt.read_bytes()).get("status") == "prepared":
                warnings.append("存在中断保存记录：" + receipt.relative_to(self.project).as_posix() + "；核对文档、board.json 和版本文件后再继续。")
        if not 4 <= len(board["palette"]) <= 6:
            warnings.append("当前不是通常的 4–6 色；确认这是用户指定的数量。")
        return warnings

    def save(self, payload):
        self.project.mkdir(parents=True, exist_ok=True)
        lock = self.project / ".moodboard-write.lock"
        try:
            handle = lock.open("x", encoding="utf-8")
        except FileExistsError:
            raise ValueError("项目已有图板正在保存；如上次进程中断，先核对保存记录与现场，再移除旧锁") from None
        try:
            with handle:
                handle.write(str(os.getpid()))
            return self._save(payload)
        finally:
            lock.unlink(missing_ok=True)

    def _save(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("保存请求须为对象")
        current, current_hash = self.read()
        if payload.get("expected") != current_hash:
            raise ValueError("磁盘图板已变化；先备份当前编辑数据，再重新打开并合并修改")
        board = validate(payload.get("board"), self.folder, allow_data=True)
        if any(board.get(k) != current.get(k) for k in ("id", "scope", "assetId")):
            raise ValueError("不能用另一块图板覆盖当前图板；请另建板或变体")
        if board["revision"] != current["revision"] + 1:
            raise ValueError("导出版本必须接续磁盘当前版本")
        if not board["references"] or not any(r["role"] == "primary" for r in board["references"]):
            raise ValueError("请先加入至少一张主要参考")
        if any(not r["viewed"] for r in board["references"]):
            raise ValueError("请实际查看每张参考，再标记为已查看")
        if not isinstance(payload.get("png"), str):
            raise ValueError("保存请求缺少 PNG")
        png = decode_image(payload["png"]) if len(payload["png"]) < 28 * 1024 * 1024 else None
        if png is None:
            raise ValueError("导出图片过大，请减少单板内容或分板")
        png_info = png_check(png)
        previous = self.document.read_bytes() if self.document.exists() else None
        old_board = self.current.read_bytes()
        token = "v" + str(board["revision"]) + "-" + uuid4().hex[:10]
        version = self.folder / "versions" / token
        for ref in board["references"]:
            data = decode_image(ref.pop("data")) if "data" in ref else contained(self.folder, ref["file"]).read_bytes()
            ref["file"] = keep_image(self.folder, data)
            ref["sha256"] = digest(data)
        updated = self.document_text(previous, board, version)
        version.mkdir(parents=True, exist_ok=False)
        atomic(version / "moodboard.png", png)
        atomic(version / "board.json", encoded(board))
        atomic(version / "current-before.json", old_board)
        if previous is not None:
            atomic(version / "art-direction-before.md", previous)
        receipt = {"status": "prepared", "revision": board["revision"], "document": self.document.relative_to(self.project).as_posix(), "documentBefore": digest(previous) if previous is not None else None, "documentAfter": digest(updated), "png": png_info, "visualReview": "not_checked"}
        atomic(version / "receipt.json", encoded(receipt))
        try:
            actual = self.document.read_bytes() if self.document.exists() else None
            if actual != previous or self.current.read_bytes() != old_board:
                raise ValueError("保存期间文档或图板被其他编辑修改；未覆盖")
            atomic(self.document, updated)
            atomic(self.current, encoded(board))
            write_bootstrap(self.folder, board)
            receipt["status"] = "saved"
            atomic(version / "receipt.json", encoded(receipt))
        except Exception:
            # Restore only bytes written by this attempt; preserve unrelated edits.
            if self.document.exists() and self.document.read_bytes() == updated:
                if previous is None:
                    self.document.unlink()
                else:
                    atomic(self.document, previous)
            if self.current.read_bytes() == encoded(board):
                atomic(self.current, old_board)
            write_bootstrap(self.folder, json.loads(self.current.read_bytes()))
            receipt["status"] = "failed"
            atomic(version / "receipt.json", encoded(receipt))
            raise
        return {"board": board, "expected": digest(self.current.read_bytes()), "png": "versions/" + token + "/moodboard.png", "config": "versions/" + token + "/board.json", "document": str(self.document), "warnings": self.warnings(board)}

    def document_text(self, previous, board, version):
        content = previous.decode("utf-8-sig") if previous is not None else "# Art Direction\n"
        start, end = (f"<!-- moodboard:{board['id']}:{suffix} -->" for suffix in ("start", "end"))
        if (start in content or end in content) and (content.count(start) != 1 or content.count(end) != 1 or content.index(start) > content.index(end)):
            raise ValueError("文档图板区块不完整；请先修复标记，未覆盖原文")
        def link(path):
            return quote(os.path.relpath(path, self.document.parent).replace("\\", "/"), safe="/.-_")
        title = board["title"].replace("[", "(").replace("]", ")").replace("<", "&lt;").replace(">", "&gt;")
        state = {"candidate": "候选", "selected": "已选用", "deferred": "暂缓"}[board["status"]]
        relation = board.get("parent")
        parent = f"关联主题 `{relation['id']}` / v{relation['revision']}。\n\n" if relation else ""
        section = (f"{start}\n### {title}\n\n![{title} · v{board['revision']}]({link(version / 'moodboard.png')})\n\n"
                   f"图板 `{board['id']}` / v{board['revision']} · {state} · {len(board['references'])} 张参考 · {len(board['palette'])} 色。\n\n{parent}"
                   f"[打开编辑页面]({link(self.folder / 'editor.html')}) · [同版本编辑数据]({link(version / 'board.json')})\n\n"
                   "方向与选用依据、来源及借鉴点保存在同版本数据。直接打开页面可编辑和下载；运行本 Skill 的本地编辑命令可保存并回写本文。图板保存不表示资产制作或游戏内验收完成。\n"
                   f"{end}")
        if start in content:
            content = content[:content.index(start)] + section + content[content.index(end) + len(end):]
        else:
            content += "\n\n" + section + "\n"
        return content.encode("utf-8")


def init_board(project, board_dir, document, board_id, scope, title, asset_id, seed=None):
    model = ProjectBoard(project, board_dir, document)
    if model.folder.exists():
        raise ValueError("图板目录已存在；使用 serve 接续，或为变体选择新目录")
    if seed:
        seed = Path(seed).resolve()
        board = validate(json.loads(seed.read_bytes()), seed.parent)
        if board["id"] != board_id or board["scope"] != scope:
            raise ValueError("初始配置与命令指定的标识/范围不一致")
    else:
        board = {"schemaVersion": 2, "id": board_id, "scope": scope, "assetId": asset_id if scope == "asset" else None,
                 "parent": None, "revision": 0, "title": title, "intent": "", "status": "candidate", "selectionBasis": "",
                 "direction": {"feeling": "", "visual": "", "dynamic": "", "avoid": "", "constraints": "", "inherit": "", "differ": ""},
                 "references": [], "palette": [{"id": "c" + str(i + 1), "name": "待定颜色 " + str(i + 1), "hex": value, "origin": "编辑占位，尚未选色"} for i, value in enumerate(("#E6E3DC", "#A8A79F", "#656963", "#303B38"))]}
        validate(board)
    model.folder.mkdir(parents=True)
    for name in ("editor.html", "style.css", "app.js", "export-image.js"):
        shutil.copy2(ASSETS / name, model.folder / name)
    for ref in board["references"]:
        data = contained(seed.parent, ref["file"]).read_bytes()
        ref["file"] = keep_image(model.folder, data)
        ref["sha256"] = digest(data)
    board["revision"] = 0
    atomic(model.current, encoded(board))
    write_bootstrap(model.folder, board)
    return model


def make_server(model, port=0):
    session_token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, data, mime="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            try:
                path = unquote(urlsplit(self.path).path).lstrip("/") or "editor.html"
                if path == "api/board":
                    board, expected = model.read()
                    return self.send(200, encoded({"board": board, "expected": expected, "warnings": model.warnings(board)}))
                if path == "art-direction":
                    return self.send(200, model.document.read_bytes(), "text/plain; charset=utf-8")
                file = contained(model.folder, path)
                if path not in {"editor.html", "style.css", "app.js", "export-image.js", "board-data.js", "board.json"} and not path.startswith(("images/", "versions/")):
                    raise ValueError("资源不在图板公开范围内")
                if path.startswith("versions/") and file.name not in {"moodboard.png", "board.json"}:
                    raise ValueError("内部保存记录不通过浏览器提供")
                data = file.read_bytes()
                mime = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(file.suffix)
                if mime is None:
                    raise ValueError("不支持的文件类型")
                if path == "editor.html":
                    data = data.replace(b"<!-- LOCAL_SESSION -->", ("<script>window.MOODBOARD_SESSION=" + json.dumps(session_token) + ";</script>").encode())
                self.send(200, data, mime)
            except (ValueError, OSError) as error:
                self.send(404, encoded({"error": str(error)}))

        def do_POST(self):
            origin = "http://127.0.0.1:" + str(self.server.server_port)
            if self.path != "/api/export" or self.headers.get("Origin") != origin or self.headers.get("X-Moodboard-Token") != session_token:
                return self.send(403, encoded({"error": "请从本地编辑页面保存"}))
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("保存数据为空或超过 80 MB；请拆分图板")
                payload = json.loads(self.rfile.read(length))
                result = model.save(payload)
                self.send(200, encoded(result))
            except (ValueError, TypeError, KeyError, OSError, zlib.error) as error:
                self.send(400, encoded({"error": str(error)}))

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "serve", "validate"))
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--board", required=True, help="Project-relative board folder, using / separators")
    parser.add_argument("--document", default="Art Direction.md")
    parser.add_argument("--id")
    parser.add_argument("--scope", choices=("game-theme", "asset"), default="game-theme")
    parser.add_argument("--title", default="待确定的美术方向")
    parser.add_argument("--asset-id", default="")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.action == "init":
            if not args.id:
                raise ValueError("init 需要 --id")
            model = init_board(args.project, args.board, args.document, args.id, args.scope, args.title, args.asset_id, args.config)
        else:
            model = ProjectBoard(args.project, args.board, args.document)
        board, _ = model.read()
        if args.action != "serve":
            print(json.dumps({"board": str(model.current), "revision": board["revision"], "warnings": model.warnings(board), "visualReview": "not_checked"}, ensure_ascii=False))
            return
        server = make_server(model, args.port)
        print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}/", "board": str(model.current)}, ensure_ascii=False), flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
