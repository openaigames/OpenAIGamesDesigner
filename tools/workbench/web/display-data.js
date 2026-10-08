// Shared presentation rules; these never change project records.
export const needsAttention=job=>['failed','blocked','interrupted','cancelled'].includes(job.status)||Boolean(job.artRegistrationError||job.versionError);
export const knownMetadata=value=>typeof value==='string'&&!['','未登记','未知','unknown'].includes(value.trim().toLowerCase());
export function artDocumentForDisplay(text){
  // File/source/status summaries remain in the human-readable asset table.
  return text.replace(/## 资产生产记录\s+此区与上方文件映射共同维护；生产状态由共享登记工具更新，历史依据链接原记录。\s*/g,'')
    .replace(/<!-- art-lifecycle:start -->[\s\S]*?<!-- art-lifecycle:end -->/g,'');
}
