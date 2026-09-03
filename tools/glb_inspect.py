"""Inspecciona un .glb sin dependencias: tamaño, triángulos, nodos, clips."""
import json, struct, sys, os

def _read_chunks(data):
    magic, version, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'no es un GLB'
    off = 12
    chunks = {}
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        chunks[ctype] = data[off + 8: off + 8 + clen]
        off += 8 + clen
    return chunks

def _prim_tris(gltf, prim):
    mode = prim.get('mode', 4)
    if 'indices' in prim:
        n = gltf['accessors'][prim['indices']]['count']
    else:
        n = gltf['accessors'][prim['attributes']['POSITION']]['count']
    if mode == 4: return n // 3
    if mode in (5, 6): return max(n - 2, 0)
    return 0

def inspect(path):
    with open(path, 'rb') as f:
        data = f.read()
    chunks = _read_chunks(data)
    gltf = json.loads(chunks[0x4E4F534A].decode('utf-8'))
    meshes = []
    for m in gltf.get('meshes', []):
        t = sum(_prim_tris(gltf, p) for p in m.get('primitives', []))
        meshes.append({'name': m.get('name', ''), 'triangles': t})
    # triángulos reales = suma por instancia de nodo
    inst = 0
    for n in gltf.get('nodes', []):
        if 'mesh' in n: inst += meshes[n['mesh']]['triangles']
    return {
        'size_bytes': os.path.getsize(path),
        'triangles': inst,
        'nodes': [n.get('name', '') for n in gltf.get('nodes', [])],
        'animations': [a.get('name', '') for a in gltf.get('animations', [])],
        'meshes': meshes,
        'skins': len(gltf.get('skins', [])),
        'images': len(gltf.get('images', [])),
        'draco': 'KHR_draco_mesh_compression' in gltf.get('extensionsUsed', []),
    }

if __name__ == '__main__':
    print(json.dumps(inspect(sys.argv[1]), indent=2, ensure_ascii=False))
