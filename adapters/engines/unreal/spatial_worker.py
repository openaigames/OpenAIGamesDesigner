"""Bounded native spatial readback for the shared observation format."""
import math
import unreal

def xyz(v):return [v.x,v.y,v.z]

def collision_objects(actor,oid):
    rows=[]
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        enabled=component.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION
        if not enabled:continue
        row={'id':oid+':'+component.get_name(),'position':xyz(component.get_world_location()),
             'kind':component.get_class().get_name(),'measurement':'engine_geometry','collision':'enabled',
             'geometry_source':component.get_path_name(),'geometry_kind':'broad_collision_bounds'}
        world=component.get_world_transform()
        # Exact native shape definitions, plus sampled outlines for visualization.
        local=[];edges=[]
        if isinstance(component,unreal.BoxComponent):
            extent=component.get_unscaled_box_extent()
            local=[unreal.Vector(x*extent.x,y*extent.y,z*extent.z) for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
            edges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]]
            row.update(geometry_kind='box',shape={'extent':xyz(extent)})
        elif isinstance(component,unreal.CapsuleComponent):
            r=component.get_unscaled_capsule_radius();h=component.get_unscaled_capsule_half_height()
            row.update(geometry_kind='capsule_outline',shape={'radius':r,'half_height':h})
            for axis in [0,1]:
                begin=len(local)
                for i in range(32):
                    a=i*math.tau/32;v=[0.,0.,r*math.sin(a)+(h-r)*(1 if math.sin(a)>=0 else -1)];v[axis]=r*math.cos(a);local.append(unreal.Vector(*v))
                edges.extend([[begin+i,begin+(i+1)%32] for i in range(32)])
        elif isinstance(component,unreal.SphereComponent):
            r=component.get_unscaled_sphere_radius();row.update(geometry_kind='sphere_outline',shape={'radius':r})
            for axis in range(3):
                begin=len(local)
                for i in range(32):
                    a=i*math.tau/32;v=[0.,0.,0.];v[axis]=r*math.cos(a);v[(axis+1)%3]=r*math.sin(a);local.append(unreal.Vector(*v))
                edges.extend([[begin+i,begin+(i+1)%32] for i in range(32)])
        if local:
            row['vertices']=[xyz(unreal.MathLibrary.transform_location(world,p)) for p in local];row['edges']=edges
            row['bounds']=[[min(v[i] for v in row['vertices']) for i in range(3)],[max(v[i] for v in row['vertices']) for i in range(3)]]
        else:
            origin,extent,_=unreal.SystemLibrary.get_component_bounds(component)
            row['bounds']=[[a-b for a,b in zip(xyz(origin),xyz(extent))],[a+b for a,b in zip(xyz(origin),xyz(extent))]]
        rows.append(row)
    return rows

def ray_queries(world,options,find_actor,time):
    rows=[]
    def position(value):
        if isinstance(value,list):return unreal.Vector(*value)
        actor=find_actor(value['target'],world)
        return actor.get_actor_location()+unreal.Vector(*value.get('offset',[0,0,0]))
    for spec in options:
        start,end=position(spec['start']),position(spec['end'])
        ignore=[find_actor(target,world) for target in spec.get('ignore',[])]
        hit=unreal.SystemLibrary.line_trace_single(world,start,end,getattr(unreal.TraceTypeQuery,'TRACE_TYPE_QUERY'+str(spec.get('channel',1))),
            spec.get('complex',False),ignore,unreal.DrawDebugTrace.NONE,False)
        row={'id':spec['id'],'object':spec['object'],'clock':'game','time':time,'start':xyz(start),'end':xyz(end),
             'blocked':hit is not None,'channel':'TraceTypeQuery'+str(spec.get('channel',1)),
             'conditions':spec['purpose']+'; '+('complex' if spec.get('complex') else 'simple')+' collision; ignores='+','.join(spec.get('ignore',[]))}
        if hit is not None:
            # Named UE BreakHitResult API layout; do not parse its printable text.
            values=hit.to_tuple()
            if len(values)<18:raise ValueError('Unsupported native HitResult tuple layout; inspect installed engine API')
            row.update(blocked=bool(values[0]),point=xyz(values[5]),normal=xyz(values[7]),hit_object=values[9].get_path_name() if values[9] else 'unknown')
        rows.append(row)
    return rows
