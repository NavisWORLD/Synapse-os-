export const FileScope = Object.freeze({
  TEMPORARY_ATTACHMENT: 'TEMPORARY_ATTACHMENT',
  CONVERSATION_CONTEXT: 'CONVERSATION_CONTEXT',
  WORKSPACE_KNOWLEDGE: 'WORKSPACE_KNOWLEDGE',
  PERSISTENT_BEAST_MEMORY: 'PERSISTENT_BEAST_MEMORY',
  VM_EPHEMERAL_STORAGE: 'VM_EPHEMERAL_STORAGE',
});

export const ScopeDescriptions = Object.freeze({
  [FileScope.TEMPORARY_ATTACHMENT]: 'Browser session only. Uploading never makes a file permanent.',
  [FileScope.CONVERSATION_CONTEXT]: 'Selected context for the active conversation.',
  [FileScope.WORKSPACE_KNOWLEDGE]: 'Explicit workspace knowledge managed through Beast.',
  [FileScope.PERSISTENT_BEAST_MEMORY]: 'Persistent continuity. Requires an explicit transfer path.',
  [FileScope.VM_EPHEMERAL_STORAGE]: 'Disposable guest storage. Destroying the machine destroys this scope.',
});
