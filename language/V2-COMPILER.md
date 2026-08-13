# Synapse Flow v2 compiler track

This branch contains the staged implementation plan and integration target for Synapse Flow v2: static types, function return values, bytecode, a stack VM, optimization, debugging, language-server diagnostics, package metadata, native-code generation for the supported typed subset, and capability-gated network/AI I/O.

Network access is denied by default. Programs must receive an explicit network capability and destination-host permission from the launcher.

The implementation is validated separately before merge into main and must preserve the existing Synapse OS VM certification gates.
