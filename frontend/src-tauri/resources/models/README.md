Build E offline AI: this folder is populated on the development/build machine by
`desktop/Stage_Bundled_Inference.ps1` after verifying independently pinned
SHA-256 values. The installer build fails if the model or inference runtime is
missing. No model is included in this source reference. The separate GGUF file,
llama.cpp Windows CPU server, DLLs and redistribution licences must be vetted.
