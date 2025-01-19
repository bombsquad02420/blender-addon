meta:
  id: bombsquad_bob
  application: BombSquad
  file-extension: bob
  endian: le
seq:
  - id: header
    type: header
  - id: mesh_info
    type: mesh_info
  - id: mesh_data
    type: mesh_data

types:
  header:
    seq:
      - id: magic
        contents: [0x37, 0xb2, 0x00, 0x00]
        doc: BOB MAGIC 45623

  mesh_info:
    seq:
      - id: mesh_format
        type: u4
        enum: e_mesh_format
        doc: |
          MeshFormat
          0 => MESH_FORMAT_UV16_N8_INDEX8
          1 => MESH_FORMAT_UV16_N8_INDEX16
          2 => MESH_FORMAT_UV16_N8_INDEX32
      - id: vertex_count
        type: u4
      - id: face_count
        type: u4

  mesh_data:
    seq:
      - id: vertices
        type: vertex
        repeat: expr
        repeat-expr: _root.mesh_info.vertex_count
      - id: faces
        type: face
        repeat: expr
        repeat-expr: _root.mesh_info.face_count

  vertex:
    seq:
      - id: pos
        type: f4
        repeat: expr
        repeat-expr: 3
      - id: uv
        type: u2
        repeat: expr
        repeat-expr: 2
      - id: norm
        type: s2
        repeat: expr
        repeat-expr: 3
      - id: padding
        contents: [0x00, 0x00]

  face:
    seq:
      - id: indices
        type:
          switch-on: _root.mesh_info.mesh_format
          cases:
            e_mesh_format::index_8: u1
            e_mesh_format::index_16: u2
            e_mesh_format::index_32: u4
        repeat: expr
        repeat-expr: 3

enums:
  e_mesh_format:
    0: index_8
    1: index_16
    2: index_32
