"""Measure triangle texture density and anisotropy in actual world meters."""
import math
from .common import number


def triangle_metrics(points, uv, size):
    if len(points) != 3 or len(uv) != 3 or len(size) != 2:
        raise ValueError('A triangle, three UV pairs, and image dimensions are required')
    for p in points:
        if len(p) != 3:
            raise ValueError('World points require XYZ meters')
        for v in p:
            number(v, 'world coordinate')
    for p in uv:
        if len(p) != 2:
            raise ValueError('UV needs two components')
        for v in p:
            number(v, 'UV coordinate')
    for v in size:
        number(v, 'image dimension', 1)
    a = [points[1][i] - points[0][i] for i in range(3)]
    b = [points[2][i] - points[0][i] for i in range(3)]
    dot = lambda x, y: sum(i*j for i, j in zip(x, y))
    length = math.sqrt(dot(a, a))
    cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
    height = math.sqrt(dot(cross, cross)) / length if length > 1e-12 else 0
    if height <= 1e-12:
        return {'area_m2': 0, 'status': 'degenerate_geometry'}
    x = dot(a, b) / length
    u = [(uv[1][i]-uv[0][i])*size[i] for i in range(2)]
    v = [(uv[2][i]-uv[0][i])*size[i] for i in range(2)]
    j = [[u[i]/length, (v[i]-u[i]*x/length)/height] for i in range(2)]
    aa = j[0][0]**2+j[1][0]**2
    bb = j[0][1]**2+j[1][1]**2
    ab = j[0][0]*j[0][1]+j[1][0]*j[1][1]
    largest = math.sqrt(max(0, (aa+bb+math.sqrt((aa-bb)**2+4*ab**2))/2))
    determinant = abs(j[0][0]*j[1][1]-j[0][1]*j[1][0])
    smallest = determinant/largest if largest > 1e-12 else 0
    return {'area_m2': length*height/2, 'status': 'ok' if smallest > 1e-10 else 'degenerate_uv',
            'texels_per_m': math.sqrt(determinant),
            'min_texels_per_m': smallest, 'max_texels_per_m': largest,
            'anisotropy': largest/smallest if smallest > 1e-10 else None}


def summarize(rows, limits=None):
    limits = limits or {}
    for key, value in limits.items():
        if key not in ('min_texels_per_m', 'max_texels_per_m', 'max_anisotropy'):
            raise ValueError('Unknown surface limit: ' + key)
        number(value, key, 0)
    area = sum(r['area_m2'] for r in rows)
    valid = [r for r in rows if r['status'] == 'ok']
    measured = sum(r['area_m2'] for r in valid)
    distribution = sorted(valid, key=lambda r: r['texels_per_m'])
    def percentile(p):
        total = 0
        for row in distribution:
            total += row['area_m2']
            if total >= measured*p:
                return row['texels_per_m']
        return None
    counts = {name: sum(r['status'] == name for r in rows)
              for name in ('ok', 'degenerate_geometry', 'degenerate_uv')}
    def affected(predicate):
        return sum(r['area_m2'] for r in valid if predicate(r)) / area if area else None
    return {'triangles': len(rows), 'area_m2': area, 'measured_area_m2': measured,
            'statuses': counts, 'density_p10': percentile(.1), 'density_p50': percentile(.5),
            'density_p90': percentile(.9),
            'below_density_area_fraction': affected(lambda r: r['texels_per_m'] < limits['min_texels_per_m']) if 'min_texels_per_m' in limits else None,
            'above_density_area_fraction': affected(lambda r: r['texels_per_m'] > limits['max_texels_per_m']) if 'max_texels_per_m' in limits else None,
            'stretched_area_fraction': affected(lambda r: r['anisotropy'] > limits['max_anisotropy']) if 'max_anisotropy' in limits else None}
