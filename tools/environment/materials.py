"""Resolve a project's surface plan and the actual files that own its settings."""
from .common import digest, inside, issue, issues_report, number, unique


def check(plan, root):
    if plan.get('schema') != 'environment-materials/1' or not plan.get('revision'):
        raise ValueError('Expected environment-materials/1 with revision')
    if not plan.get('style') or not plan.get('basis'):
        raise ValueError('Record the selected style and its existing basis')
    materials = unique(plan.get('materials', []))
    sources = unique(plan.get('sources', []))
    regions = unique(plan.get('regions', []))
    issues, files, owners = [], {}, {}
    for sid, source in sources.items():
        for field in ('kind', 'path', 'consumer'):
            if not source.get(field):
                raise ValueError(sid + ' needs ' + field)
        files[source['path']] = digest(inside(root, source['path']))
        for parameter in source.get('parameters', []):
            if not isinstance(parameter, str) or not parameter:
                raise ValueError('Parameter names must be nonempty strings')
            key = (source['consumer'], parameter)
            if key in owners:
                issues.append(issue('multiple_parameter_owners', consumer=key[0], parameter=parameter,
                                    sources=[owners[key], sid]))
            owners[key] = sid
    for mid, material in materials.items():
        if not material.get('purpose'):
            issues.append(issue('material_purpose_missing', material=mid))
        for key in ('roughness', 'metallic'):
            if key in material:
                number(material[key], key, 0, 1)
        for key in ('tile_size_m', 'texels_per_m'):
            if key in material:
                number(material[key], key, 1e-12)
        for ref in material.get('source_ids', []):
            if ref not in sources:
                issues.append(issue('unknown_material_source', material=mid, source=ref))
        for key in ('scale_basis', 'variation', 'wear', 'lighting_response'):
            if not material.get(key):
                issues.append(issue('surface_decision_unrecorded', 'warning', material=mid, field=key))
    for rid, region in regions.items():
        for mid in region.get('materials', []):
            if mid not in materials:
                issues.append(issue('unknown_region_material', region=rid, material=mid))
        if not region.get('sample_views'):
            issues.append(issue('representative_view_missing', 'warning', region=rid))
    return issues_report('environment-material-report', issues, revision=plan['revision'],
                         files=files, material_count=len(materials), region_count=len(regions),
                         sources=list(sources.values()),
                         note='Values are declared production choices. Sample renders and engine readback remain separate evidence.')
