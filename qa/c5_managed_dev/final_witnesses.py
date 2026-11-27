"""Exact final Rust/browser command projections, not execution authority."""
from pathlib import Path
from . import validation_witnesses as w

LIVE_ENABLED = False
RUST_SOURCE = 'frontend/src-tauri/src/storage_profile_tests.rs'
RUST_SOURCE_BLOB = '1f79beebbc2979d0d0f04e5726661c8aefcb5c12'
P1_SELECTORS = ('real HTTP import, Quality, rejected switch',
                'real HTTP Quality approval, keyboard consent',
                'real HTTP reversible project management',
                'real HTTP B5 export')
P4_EXCLUDED = 'BE-024 real HTTP: reopen a fitted synthetic experiment'


def rust_commands(rustc, profile_id, source, scratch):
    w.need(all(Path(p).is_absolute() for p in (rustc,source,scratch)), 'RUST_PATH')
    w.need(w.blob(Path(source).read_bytes()) == RUST_SOURCE_BLOB, 'RUST_SOURCE')
    base = (str(rustc),'--edition=2021','--test',str(source))
    if profile_id == 'windows-x64-cp311-source-test':
        output = Path(scratch)/'pilotodin-storage-policy.obj'
        return (base+('--emit=obj','-o',str(output)),), output
    w.need(profile_id == 'linux-x64-cp311-source-test','RUST_PROFILE')
    output = Path(scratch)/'pilotodin-storage-policy-tests'
    return (base+('-o',str(output)),(str(output),)), output


def browser_commands(node, frontend):
    w.need(Path(node).is_absolute() and Path(frontend).is_absolute(),'BROWSER_PATH')
    cli = Path(frontend)/'node_modules/playwright/cli.js'
    base = (str(node),str(cli),'test')
    return tuple(base+('--config=playwright.c5-p1-real-http.config.ts','-g',selector)
                 for selector in P1_SELECTORS)+(base+('--config=playwright.c5-p4-real-http.config.ts',
                                                     '--grep-invert',P4_EXCLUDED),)


if __name__ == '__main__':
    raise SystemExit('FINAL_WITNESSES_DISARMED')
