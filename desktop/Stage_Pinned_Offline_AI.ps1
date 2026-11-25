# PilotODIN C5: this legacy mutating entrypoint is frozen before setup.
# Previous implementation retained at 898230f116266e064f6925c03d538c8e3b863f7e:desktop/Stage_Pinned_Offline_AI.ps1.
# A separately reviewed exact-input contract and explicit scope are required.
# Historical pins (not new verification or permission): llama.cpp b10344 / 7a20b417f4526cae073bd997af5020cea3e7ccbe
# Archive SHA256 c0cec8825843957cae6620f927eb6eb9f7f4680da3206910932ea9075f91b405
# Qwen3-1.7B Q4_K_M revision daeb8e2d528a760970442092f6bf1e55c3b659eb
# Model SHA256 d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5
Write-Error 'STOP: C5_AI_ACQUISITION_BLOCKED; independent runtime inventory and separate acquisition approval required.' -ErrorAction Continue
exit 2
