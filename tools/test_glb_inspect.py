import json, struct, unittest, tempfile, os
from glb_inspect import inspect

def make_glb(tmp):
    # GLB mínimo: 1 malla con 2 triángulos (6 índices uint16), 1 nodo, 1 animación
    idx = struct.pack('<6H', 0,1,2, 0,2,3)
    idx += b'\x00\x00'  # padding a 4 bytes
    pos = struct.pack('<12f', 0,0,0, 1,0,0, 1,1,0, 0,1,0)
    bin_chunk = idx + pos
    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(bin_chunk)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 12},
            {"buffer": 0, "byteOffset": 16, "byteLength": 48}],
        "accessors": [
            {"bufferView": 0, "componentType": 5123, "count": 6, "type": "SCALAR"},
            {"bufferView": 1, "componentType": 5126, "count": 4, "type": "VEC3"}],
        "meshes": [{"name": "Quad", "primitives": [{"attributes": {"POSITION": 1}, "indices": 0}]}],
        "nodes": [{"name": "QuadNode", "mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "animations": [{"name": "typing", "channels": [], "samplers": []}],
    }
    js = json.dumps(gltf).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    body = struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bin_chunk), 0x004E4942) + bin_chunk
    data = struct.pack('<III', 0x46546C67, 2, 12 + len(body)) + body
    p = os.path.join(tmp, 't.glb')
    with open(p, 'wb') as f:
        f.write(data)
    return p

class T(unittest.TestCase):
    def test_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = inspect(make_glb(tmp))
        self.assertEqual(r['triangles'], 2)
        self.assertEqual(r['nodes'], ['QuadNode'])
        self.assertEqual(r['animations'], ['typing'])
        self.assertEqual(r['meshes'], [{'name': 'Quad', 'triangles': 2}])
        self.assertGreater(r['size_bytes'], 0)

if __name__ == '__main__':
    unittest.main()
