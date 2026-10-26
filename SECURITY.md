# Security and privacy

Core checks and fixing run locally. No network client, telemetry, shell interpolation, LLM call,
remote policy include or automatic package installation exists in the engine. Config uses a
bounded SafeLoader with duplicate-key detection and aliases disabled. Configs and regexes are
trusted inputs; Python regex does not provide a timeout.

Symlink files/directories and Git submodules are not followed by enumeration; skipped symlink
files appear in JSON. Explicit/config paths through symlinks and parent traversal are rejected.
Fixes reject hardlinks and perform a concurrent-change check and adjacent atomic replacement.
These are defensive checks, not a sandbox against another process racing parent directory swaps.
Use an isolated filesystem/container against actively hostile repositories or concurrent writers.

Text checks fail explicitly on binary/invalid UTF-8/oversized matching input. Unmatched binary
files can still be checked by path/size policies. Reports avoid core source excerpts; external
tool messages may contain repository content. Treat report/artifact publication as a separate
authorized action. The AF bridge sets `publish: false` and performs no upload.

External tools run only with explicit `--allow-plugins`, inherit caller environment/permissions
and may access services or write files. Audit their commands and native configs. For server-side
checks use pinned tools in an ephemeral, network-disabled, read-only container without secrets,
plus CPU/memory/disk/time limits. Tool process timeout and bounded output reads do not provide
full containment. All file arguments are distinct argv entries; too-large argv fails explicitly.

Engine `fix` does not invoke tool fixes; it never strips whitespace or reformats language files.
Appending a final newline can matter for byte-sensitive formats, signatures, fixtures, checksums,
ACLs or xattrs. Opt into it only for intended text files; keep such assets check-only/excluded.

Before webhook enforcement, use policy from a reviewed/protected base, not an untrusted head
that can weaken its own gate. Validate webhook signatures, resource scope, identities, exact SHA,
event deduplication and status publication credentials. See `docs/platform-backlog.md`.
