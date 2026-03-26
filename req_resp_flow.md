# Client Request/Response Flow

This document describes the full request/response cycle for a client that wants to:

1. Copy input data from shared storage into the storeBase
2. Run a plugin on that data
3. Get output file metadata
4. Upload output data back to shared storage (Swift only)
5. Delete all job data from the storeBase
6. Remove all containers

All endpoints are prefixed with `/api/v1/`.

---

## 0. Authenticate

```
POST /api/v1/auth-token/
Content-Type: application/json

{
  "pfcon_user": "pfcon",
  "pfcon_password": "pfcon1234"
}
```

**Response** `200 OK`:
```json
{
  "token": "<JWT>"
}
```

All subsequent requests include `Authorization: Bearer <JWT>`.

---

## Flow for `fslink` storage

In fslink mode, data lives on a shared POSIX filesystem. Copy pulls files (resolving `.chrislink` files) into the storeBase. Upload is a no-op because the output is already on the shared filesystem.

### 1. Schedule copy job

```
POST /api/v1/copyjobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
&input_dirs=<swift_or_fs_path_1>
&input_dirs=<swift_or_fs_path_2>   (optional, repeatable)
&output_dir=<output_path>
&cpu_limit=1000                     (optional, default 1000)
&memory_limit=200                   (optional, default 200)
```

- `input_dirs`: one or more paths relative to the storeBase root (e.g. `home/alice/feed_42/pl-dircopy_85/data`)
- `output_dir`: path where the client expects output to land (e.g. `home/alice/feed_42/pl-simplefsapp_86/data`)

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.copy_worker /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

The copy container runs asynchronously. It reads `input_dirs` from the shared filesystem, resolves any `.chrislink` files recursively, and writes the resolved tree to `<storeBase>/key-<job_id>/incoming/`.

### 2. Poll copy status

```
GET /api/v1/copyjobs/<job_id>/
Authorization: Bearer <JWT>
```

**Response** `200 OK`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.copy_worker /share/outgoing",
    "status": "finishedSuccessfully",
    "message": "",
    "timestamp": "2026-03-12T10:30:00",
    "logs": "..."
  }
}
```

Possible `status` values: `notStarted`, `started`, `finishedSuccessfully`, `finishedWithError`, `undefined`.

Poll until `status` is `finishedSuccessfully` or `finishedWithError`.

### 3. Schedule plugin job

```
POST /api/v1/pluginjobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
&entrypoint=python3
&entrypoint=/usr/local/bin/simplefsapp
&args=--dir
&args=/share/incoming
&auid=cube
&number_of_workers=1
&cpu_limit=1000
&memory_limit=200
&gpu_limit=0
&image=fnndsc/pl-simplefsapp
&type=fs
&input_dirs=<input_path>
&output_dir=<output_path>
```

- `entrypoint`: repeatable, forms the command prefix
- `args`: repeatable, forms the argument list
- `type`: `fs` (no input mount), `ds` (input dir appended to cmd), or `ts`
- `input_dirs`, `output_dir`: same paths as the copy job (used by pfcon to know where the client's data lives)

**Response** `201 Created`:
```json
{
  "data": {},
  "compute": {
    "jid": "<job_id>",
    "image": "fnndsc/pl-simplefsapp",
    "cmd": "python3 /usr/local/bin/simplefsapp --dir /share/incoming /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

The plugin container mounts:
- `<storeBase>/key-<job_id>/incoming` -> `/share/incoming`
- `<output_dir>` -> `/share/outgoing`

### 4. Poll plugin status

```
GET /api/v1/pluginjobs/<job_id>/
Authorization: Bearer <JWT>
```

**Response** `200 OK`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "fnndsc/pl-simplefsapp",
    "cmd": "python3 /usr/local/bin/simplefsapp --dir /share/incoming /share/outgoing",
    "status": "finishedSuccessfully",
    "message": "",
    "timestamp": "2026-03-12T10:31:00",
    "logs": "..."
  }
}
```

### 5. Get output file metadata

```
GET /api/v1/pluginjobs/<job_id>/file/?job_output_path=<output_path>
Authorization: Bearer <JWT>
```

**Response** `200 OK` (`application/json`):
```json
{
  "job_output_path": "<output_path>",
  "rel_file_paths": [
    "output_file_1.txt",
    "subdir/output_file_2.txt"
  ]
}
```

Returns the list of relative file paths in the output directory. The client uses this to know what files the plugin produced.

### 6. Upload output (no-op for fslink)

```
POST /api/v1/uploadjobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
&job_output_path=<output_path>
```

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "",
    "cmd": "",
    "status": "finishedSuccessfully",
    "message": "uploadSkipped",
    "timestamp": "",
    "logs": ""
  }
}
```

Since the output is already on the shared filesystem, no upload container is scheduled. The response is immediate.

### 7. Schedule delete job

```
POST /api/v1/deletejobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
```

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.delete_worker /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

The delete container removes `<storeBase>/key-<job_id>/` (both `incoming/` and any intermediate data).

### 8. Poll delete status

```
GET /api/v1/deletejobs/<job_id>/
Authorization: Bearer <JWT>
```

**Response** `200 OK`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.delete_worker /share/outgoing",
    "status": "finishedSuccessfully",
    "message": "",
    "timestamp": "2026-03-12T10:32:00",
    "logs": "..."
  }
}
```

### 9. Remove all containers

```
DELETE /api/v1/copyjobs/<job_id>/
Authorization: Bearer <JWT>
```
**Response** `204 No Content`

```
DELETE /api/v1/pluginjobs/<job_id>/
Authorization: Bearer <JWT>
```
**Response** `204 No Content`

```
DELETE /api/v1/uploadjobs/<job_id>/
Authorization: Bearer <JWT>
```
**Response** `204 No Content` (no-op since no container was created)

```
DELETE /api/v1/deletejobs/<job_id>/
Authorization: Bearer <JWT>
```
**Response** `204 No Content`

---

## Flow for `swift` storage

In Swift mode, input data lives in OpenStack Swift object storage. Copy pulls objects from Swift into the storeBase. After the plugin runs, upload pushes output back to Swift.

### 1. Schedule copy job

```
POST /api/v1/copyjobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
&input_dirs=<swift_prefix_1>
&input_dirs=<swift_prefix_2>        (optional, repeatable)
&output_dir=<swift_output_prefix>
```

- `input_dirs`: Swift object prefixes (e.g. `home/alice/feed_42/pl-dircopy_85/data`)
- `output_dir`: Swift prefix where output will eventually be uploaded (e.g. `home/alice/feed_42/pl-simplefsapp_86/data`)

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.copy_worker /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

The copy container downloads all objects matching `input_dirs` from Swift, resolves `.chrislink` files recursively, and writes the result to `<storeBase>/key-<job_id>/incoming/`.

### 2. Poll copy status

Same as fslink (see above).

### 3. Schedule plugin job

```
POST /api/v1/pluginjobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
&entrypoint=python3
&entrypoint=/usr/local/bin/simplefsapp
&args=--dir
&args=/share/incoming
&auid=cube
&number_of_workers=1
&cpu_limit=1000
&memory_limit=200
&gpu_limit=0
&image=fnndsc/pl-simplefsapp
&type=fs
&input_dirs=<swift_input_prefix>
&output_dir=<swift_output_prefix>
```

**Response** `201 Created`:
```json
{
  "data": {},
  "compute": {
    "jid": "<job_id>",
    "image": "fnndsc/pl-simplefsapp",
    "cmd": "python3 /usr/local/bin/simplefsapp --dir /share/incoming /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

In Swift mode the plugin container mounts:
- `<storeBase>/key-<job_id>/incoming` -> `/share/incoming`
- `<storeBase>/key-<job_id>/outgoing` -> `/share/outgoing`

Note: unlike fslink, the output goes to a `key-<job_id>/outgoing` directory (not the `output_dir` path directly) because it still needs to be uploaded to Swift.

### 4. Poll plugin status

Same as fslink (see above).

### 5. Get output file metadata

```
GET /api/v1/pluginjobs/<job_id>/file/?job_output_path=<swift_output_prefix>
Authorization: Bearer <JWT>
```

**Response** `200 OK` (`application/json`):
```json
{
  "job_output_path": "<swift_output_prefix>",
  "rel_file_paths": [
    "output_file_1.txt",
    "subdir/output_file_2.txt"
  ]
}
```

### 6. Upload output to Swift

```
POST /api/v1/uploadjobs/
Content-Type: application/x-www-form-urlencoded

jid=<job_id>
&job_output_path=<swift_output_prefix>
```

- `job_output_path`: the Swift prefix where output files should be uploaded

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.upload_worker /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

The upload container reads files from `<storeBase>/key-<job_id>/outgoing/` and uploads them to Swift under the `job_output_path` prefix.

This endpoint is **idempotent**: if the upload container already exists and hasn't failed, a repeated POST returns the existing container's status instead of scheduling a duplicate.

### 7. Poll upload status

```
GET /api/v1/uploadjobs/<job_id>/
Authorization: Bearer <JWT>
```

**Response** `200 OK`:
```json
{
  "compute": {
    "jid": "<job_id>",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.upload_worker /share/outgoing",
    "status": "finishedSuccessfully",
    "message": "",
    "timestamp": "2026-03-12T10:33:00",
    "logs": "..."
  }
}
```

### 8. Schedule delete job

Same as fslink (see above). Removes `<storeBase>/key-<job_id>/`.

### 9. Poll delete status

Same as fslink (see above).

### 10. Remove all containers

```
DELETE /api/v1/copyjobs/<job_id>/
```
**Response** `204 No Content`

```
DELETE /api/v1/pluginjobs/<job_id>/
```
**Response** `204 No Content`

```
DELETE /api/v1/uploadjobs/<job_id>/
```
**Response** `204 No Content`

```
DELETE /api/v1/deletejobs/<job_id>/
```
**Response** `204 No Content`

---

## Sequence diagrams

### fslink

```
Client                          pfcon                        Compute Cluster       Shared FS
  |                               |                               |                   |
  |-- POST /auth-token/ -------->|                               |                   |
  |<-------- 200 {token} --------|                               |                   |
  |                               |                               |                   |
  |-- POST /copyjobs/ ---------->|                               |                   |
  |                               |-- schedule copy container -->|                   |
  |<-------- 201 {notStarted} ---|                               |                   |
  |                               |                               |-- resolve links ->|
  |                               |                               |-- write incoming ->|
  |-- GET /copyjobs/<id>/ ------>|-- query container status ---->|                   |
  |<-------- 200 {finished} -----|                               |                   |
  |                               |                               |                   |
  |-- POST /pluginjobs/ -------->|                               |                   |
  |                               |-- schedule plugin container ->|                   |
  |<-------- 201 {notStarted} ---|                               |                   |
  |                               |                               |-- read incoming -->|
  |                               |                               |-- write outgoing ->|
  |-- GET /pluginjobs/<id>/ ---->|-- query container status ---->|                   |
  |<-------- 200 {finished} -----|                               |                   |
  |                               |                               |                   |
  |-- GET /pluginjobs/<id>/file/ >|                               |                   |
  |<-------- 200 {file list} ----|                               |                   |
  |                               |                               |                   |
  |-- POST /uploadjobs/ -------->|                               |                   |
  |<-- 201 {uploadSkipped} ------|  (no-op: output already on FS)|                   |
  |                               |                               |                   |
  |-- POST /deletejobs/ -------->|                               |                   |
  |                               |-- schedule delete container ->|                   |
  |<-------- 201 {notStarted} ---|                               |                   |
  |                               |                               |-- rm key dir ---->|
  |-- GET /deletejobs/<id>/ ---->|-- query container status ---->|                   |
  |<-------- 200 {finished} -----|                               |                   |
  |                               |                               |                   |
  |-- DELETE /copyjobs/<id>/ --->|-- remove container ---------->|                   |
  |<-------- 204 ----------------|                               |                   |
  |-- DELETE /pluginjobs/<id>/ ->|-- remove container ---------->|                   |
  |<-------- 204 ----------------|                               |                   |
  |-- DELETE /deletejobs/<id>/ ->|-- remove container ---------->|                   |
  |<-------- 204 ----------------|                               |                   |
```

### swift

```
Client                          pfcon                        Compute Cluster       Swift
  |                               |                               |                  |
  |-- POST /auth-token/ -------->|                               |                  |
  |<-------- 200 {token} --------|                               |                  |
  |                               |                               |                  |
  |-- POST /copyjobs/ ---------->|                               |                  |
  |                               |-- schedule copy container -->|                  |
  |<-------- 201 {notStarted} ---|                               |                  |
  |                               |                               |-- download ----->|
  |                               |                               |   objects        |
  |                               |                               |-- resolve links  |
  |                               |                               |-- write incoming |
  |-- GET /copyjobs/<id>/ ------>|-- query container status ---->|                  |
  |<-------- 200 {finished} -----|                               |                  |
  |                               |                               |                  |
  |-- POST /pluginjobs/ -------->|                               |                  |
  |                               |-- schedule plugin container ->|                  |
  |<-------- 201 {notStarted} ---|                               |                  |
  |                               |                               |-- read incoming  |
  |                               |                               |-- write outgoing |
  |-- GET /pluginjobs/<id>/ ---->|-- query container status ---->|                  |
  |<-------- 200 {finished} -----|                               |                  |
  |                               |                               |                  |
  |-- GET /pluginjobs/<id>/file/ >|                               |                  |
  |<-------- 200 {file list} ----|                               |                  |
  |                               |                               |                  |
  |-- POST /uploadjobs/ -------->|                               |                  |
  |                               |-- schedule upload container ->|                  |
  |<-------- 201 {notStarted} ---|                               |                  |
  |                               |                               |-- upload ------->|
  |                               |                               |   objects        |
  |-- GET /uploadjobs/<id>/ ---->|-- query container status ---->|                  |
  |<-------- 200 {finished} -----|                               |                  |
  |                               |                               |                  |
  |-- POST /deletejobs/ -------->|                               |                  |
  |                               |-- schedule delete container ->|                  |
  |<-------- 201 {notStarted} ---|                               |                  |
  |                               |                               |-- rm key dir     |
  |-- GET /deletejobs/<id>/ ---->|-- query container status ---->|                  |
  |<-------- 200 {finished} -----|                               |                  |
  |                               |                               |                  |
  |-- DELETE /copyjobs/<id>/ --->|-- remove container ---------->|                  |
  |<-------- 204 ----------------|                               |                  |
  |-- DELETE /pluginjobs/<id>/ ->|-- remove container ---------->|                  |
  |<-------- 204 ----------------|                               |                  |
  |-- DELETE /uploadjobs/<id>/ ->|-- remove container ---------->|                  |
  |<-------- 204 ----------------|                               |                  |
  |-- DELETE /deletejobs/<id>/ ->|-- remove container ---------->|                  |
  |<-------- 204 ----------------|                               |                  |
```

---

## Key differences between fslink and swift

| Aspect | fslink | swift |
|---|---|---|
| Copy source | Shared POSIX filesystem | Swift object storage |
| Plugin output dir | `<output_dir>` (directly on shared FS) | `key-<job_id>/outgoing` (local storeBase) |
| Upload step | No-op (`uploadSkipped`) | Schedules upload container to push to Swift |
| Upload idempotency | N/A | Yes - repeated POST returns existing status |
| `.chrislink` resolution | Follows symlink-like files on filesystem | Downloads and follows `.chrislink` objects from Swift |
| Containers created | 3 (copy, plugin, delete) | 4 (copy, plugin, upload, delete) |
| Network connectivity | Containers need storeBase mount only | Copy/upload containers also need Swift network access |

---

## Concrete example: fslink with `pl-simpledsapp`

This example assumes:
- The repo is cloned at `/home/user/pfcon_fork`
- The server was started with `./make.sh -N -F fslink` from that directory
- pfcon is reachable at `http://localhost:30006`
- STOREBASE defaults to `/home/user/pfcon_fork/CHRIS_REMOTE_FS`

### Setup: create test data on the shared filesystem

```bash
STOREBASE=/home/user/pfcon_fork/CHRIS_REMOTE_FS

# Create the input folder with a test file
mkdir -p $STOREBASE/home/user/cube/test
echo "test file" > $STOREBASE/home/user/cube/test/test_file.txt

# Create a .chrislink file in home/user/cube pointing to the test folder
echo "home/user/cube/test" > $STOREBASE/home/user/cube/test.chrislink

# Create the output directory (required in fslink mode — plugin writes directly here)
mkdir -p $STOREBASE/home/user/cube_out
```

Resulting layout under STOREBASE:
```
CHRIS_REMOTE_FS/
└── home/user/cube/
    ├── test/
    │   └── test_file.txt          # content: "test file"
    └── test.chrislink             # content: "home/user/cube/test"
```

### Step 0: Authenticate

```bash
TOKEN=$(curl -s -X POST http://localhost:30006/api/v1/auth-token/ \
  -H 'Content-Type: application/json' \
  -d '{"pfcon_user":"pfcon","pfcon_password":"pfcon1234"}' \
  | jq -r '.token')
```

### Step 1: Schedule copy job

```bash
curl -s -X POST http://localhost:30006/api/v1/copyjobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -d 'jid=chris-jid-2&input_dirs=home/user/cube&output_dir=home/user/cube_out'
```

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "chris-jid-2",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.copy_worker /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

The copy worker reads `home/user/cube/`, finds `test.chrislink`, follows it to `home/user/cube/test/`, and writes the resolved tree to `CHRIS_REMOTE_FS/key-chris-jid-2/incoming/`. The `test/` folder content is placed under a subdirectory named after the link file stem (`test/`).

### Step 2: Poll copy status

```bash
curl -s http://localhost:30006/api/v1/copyjobs/chris-jid-2/ \
  -H "Authorization: Bearer $TOKEN"
```

Poll until `status` is `finishedSuccessfully`. At that point the storeBase contains:
```
CHRIS_REMOTE_FS/key-chris-jid-2/incoming/
├── test_file.txt          # from home/user/cube/test/ (direct files)
└── test/                  # resolved from test.chrislink
    └── test_file.txt
```

### Step 3: Schedule plugin job

```bash
curl -s -X POST http://localhost:30006/api/v1/pluginjobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -d 'jid=chris-jid-2
&args=--prefix
&args=le
&auid=cube
&number_of_workers=1
&cpu_limit=1000
&memory_limit=200
&gpu_limit=0
&image=fnndsc/pl-simpledsapp
&entrypoint=python3
&entrypoint=/usr/local/bin/simpledsapp
&type=ds
&input_dirs=home/user/cube
&output_dir=home/user/cube_out'
```

Or as a single line:

```bash
curl -s -X POST http://localhost:30006/api/v1/pluginjobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -d 'jid=chris-jid-2&args=--prefix&args=le&auid=cube&number_of_workers=1&cpu_limit=1000&memory_limit=200&gpu_limit=0&image=fnndsc/pl-simpledsapp&entrypoint=python3&entrypoint=/usr/local/bin/simpledsapp&type=ds&input_dirs=home/user/cube&output_dir=home/user/cube_out'
```

**Response** `201 Created`:
```json
{
  "data": {},
  "compute": {
    "jid": "chris-jid-2",
    "image": "fnndsc/pl-simpledsapp",
    "cmd": "python3 /usr/local/bin/simpledsapp --prefix le /share/incoming /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

For `type=ds`, pfcon appends `/share/incoming /share/outgoing` to the command after the plugin args. The container mounts:
- `CHRIS_REMOTE_FS/key-chris-jid-2/incoming` → `/share/incoming`
- `CHRIS_REMOTE_FS/home/user/cube_out` → `/share/outgoing`  *(output goes directly to the shared FS in fslink mode)*

### Step 4: Poll plugin status

```bash
curl -s http://localhost:30006/api/v1/pluginjobs/chris-jid-2/ \
  -H "Authorization: Bearer $TOKEN"
```

Poll until `status` is `finishedSuccessfully`.

### Step 5: Get output file metadata

```bash
curl -s "http://localhost:30006/api/v1/pluginjobs/chris-jid-2/file/?job_output_path=home/user/cube_out" \
  -H "Authorization: Bearer $TOKEN"
```

**Response** `200 OK`:
```json
{
  "job_output_path": "home/user/cube_out",
  "rel_file_paths": [
    "test_file_le.txt",
    "test/test_file_le.txt"
  ]
}
```

### Step 6: Upload output (no-op for fslink)

```bash
curl -s -X POST http://localhost:30006/api/v1/uploadjobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -d 'jid=chris-jid-2&job_output_path=home/user/cube_out'
```

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "chris-jid-2",
    "image": "",
    "cmd": "",
    "status": "finishedSuccessfully",
    "message": "uploadSkipped",
    "timestamp": "",
    "logs": ""
  }
}
```

Output is already on the shared filesystem — no upload container is launched.

### Step 7: Schedule delete job

```bash
curl -s -X POST http://localhost:30006/api/v1/deletejobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -d 'jid=chris-jid-2'
```

**Response** `201 Created`:
```json
{
  "compute": {
    "jid": "chris-jid-2",
    "image": "ghcr.io/fnndsc/pfconopjob",
    "cmd": "python -m pfcon.delete_worker /share/outgoing",
    "status": "notStarted",
    "message": "",
    "timestamp": "",
    "logs": ""
  }
}
```

### Step 8: Poll delete status

```bash
curl -s http://localhost:30006/api/v1/deletejobs/chris-jid-2/ \
  -H "Authorization: Bearer $TOKEN"
```

Poll until `status` is `finishedSuccessfully`. After this, `CHRIS_REMOTE_FS/key-chris-jid-2/incoming/`, `outgoing/`, and all param files are removed. The empty `key-chris-jid-2/` directory itself remains on disk.

### Step 9: Remove all containers

```bash
curl -s -X DELETE http://localhost:30006/api/v1/copyjobs/chris-jid-2/ \
  -H "Authorization: Bearer $TOKEN"
# 204 No Content

curl -s -X DELETE http://localhost:30006/api/v1/pluginjobs/chris-jid-2/ \
  -H "Authorization: Bearer $TOKEN"
# 204 No Content

curl -s -X DELETE http://localhost:30006/api/v1/deletejobs/chris-jid-2/ \
  -H "Authorization: Bearer $TOKEN"
# 204 No Content
```
