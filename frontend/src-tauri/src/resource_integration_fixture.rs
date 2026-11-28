//! Separately approved synthetic integration test. Never run as ordinary CI.
use crate::{NativeReportSave, write_verified_report};
use crate::resource_shell::{InferenceGroup, ShellChannel, ShellDriver};
use crate::resource_supervisor::{Factory, StartupOutcome, Supervisor};
use crate::resource_transport::Transport;
use crate::resource_wire::{Wire, SaveKind};
use crate::resource_save::SaveTicket;
use std::{fs, io::Write, path::{Path, PathBuf}, sync::{Arc, Mutex, mpsc},
          sync::atomic::{AtomicUsize, Ordering}, thread, time::{Duration, Instant}};
use tauri_plugin_shell::{ShellExt, process::OwnedJob};
use std::path::{Component, Prefix};

// canonicalize() yields a Windows verbatim prefix. Compare that identity,
// but pass the checked, ordinary drive spelling to the workspace boundary.
fn ordinary_drive(path: &Path) -> bool {
    path.is_absolute() && matches!(path.components().next(),
        Some(Component::Prefix(prefix)) if matches!(prefix.kind(), Prefix::Disk(_)))
        && !path.components().any(|part| matches!(part, Component::ParentDir))
}

fn mark(root: &Path, name: &str) {
    let mut out = fs::OpenOptions::new().write(true).create_new(true)
        .open(root.join(name)).expect("fixture marker");
    out.write_all(b"fixture\n").unwrap();
}

fn wait_file(root: &Path, name: &str) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(25);
    while !root.join(name).is_file() {
        if Instant::now() >= deadline { return Err("Synthetic barrier expired".into()); }
        thread::sleep(Duration::from_millis(20));
    }
    Ok(())
}

fn tick_until(s: &mut Supervisor<()>, mut predicate: impl FnMut(&Supervisor<()>) -> bool) {
    let deadline = Instant::now() + Duration::from_secs(25);
    loop {
        s.tick().expect("actual private host tick");
        if predicate(s) { return; }
        assert!(Instant::now() < deadline, "synthetic lifecycle deadline");
        thread::sleep(Duration::from_millis(10));
    }
}

fn reserve(s: &mut Supervisor<()>, kind: SaveKind) -> SaveTicket {
    let deadline = Instant::now() + Duration::from_secs(8);
    loop {
        if let Ok(ticket) = s.reserve_save(kind) { return ticket; }
        s.tick().expect("fixture reserve tick");
        assert!(Instant::now() < deadline, "fixture reservation deadline");
        thread::sleep(Duration::from_millis(10));
    }
}

#[test]
#[ignore = "requires one exact native owned-host synthetic approval"]
fn actual_owned_pipe_job_and_writer_lifecycle() {
    assert_eq!(std::env::var("GITHUB_ACTIONS").as_deref(), Ok("true"));
    assert_eq!(std::env::var("GITHUB_RUN_ATTEMPT").as_deref(), Ok("1"));
    assert_eq!(std::env::var("PILOTODIN_C1_C2_FIXTURE_APPROVAL").as_deref(),
               Ok("OWNED_HOST_SYNTHETIC_ONCE"));
    let fixture_base = PathBuf::from(std::env::var_os("PILOTODIN_C1_C2_FIXTURE_ROOT").unwrap());
    let runner = PathBuf::from(std::env::var_os("RUNNER_TEMP").unwrap());
    assert!(ordinary_drive(&fixture_base) && ordinary_drive(&runner));
    let base_identity = fixture_base.canonicalize().unwrap();
    assert_eq!(base_identity.parent(), Some(runner.canonicalize().unwrap().as_path()));
    assert_eq!(fixture_base.parent(), Some(runner.as_path()));
    assert!(fs::read_dir(&fixture_base).unwrap().next().is_none());
    let root = fixture_base.join(format!("owned-host-{}", uuid::Uuid::new_v4()));
    fs::create_dir(&root).unwrap();
    assert_eq!(root.canonicalize().unwrap().parent(), Some(base_identity.as_path()));
    let python = PathBuf::from(std::env::var_os("PILOTODIN_C1_C2_FIXTURE_PYTHON").unwrap());
    assert!(ordinary_drive(&python) && python.is_file());
    let repo = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().parent().unwrap();
    let script = repo.join("qa/c1_c2_owned_host_fixture.py");
    assert!(ordinary_drive(&script) && script.is_file());

    // No application event loop, webview, IPC or production resource gate.
    let app = tauri::test::mock_builder()
        .plugin(tauri_plugin_shell::init())
        .build(tauri::test::mock_context(tauri::test::noop_assets())).unwrap();
    let generation = uuid::Uuid::new_v4().simple().to_string();
    let capability = format!("{}{}",uuid::Uuid::new_v4().simple(),uuid::Uuid::new_v4().simple());
    let make = |role: &str| app.shell().command(&python)
        .args(["-I", "-B"]).arg(&script).arg(role).arg(&root)
        .current_dir(&root).set_raw_out(true).set_process_group(true).kill_on_drop(true);
    let engine = make("engine").env("PILOTODIN_DESKTOP_WATCH_STDIN","1")
        .env("PILOTODIN_CONTROL_GENERATION",&generation)
        .env("PILOTODIN_CONTROL_CAPABILITY",&capability);
    let worker = Mutex::new(Some(make("worker")));
    let observed_job: Arc<Mutex<Option<OwnedJob>>> = Arc::new(Mutex::new(None));
    let job = observed_job.clone();
    let launches = Arc::new(AtomicUsize::new(0));
    let count = launches.clone();
    let factory: Factory<()> = Arc::new(move |cancelled| {
        if cancelled.load(Ordering::Acquire) { return StartupOutcome::NeverStarted; }
        let Some(command) = worker.lock().unwrap().take() else { return StartupOutcome::Uncertain(()); };
        count.fetch_add(1, Ordering::AcqRel);
        match command.spawn() {
            Ok((events, child)) => {
                *job.lock().unwrap() = child.owned_job();
                StartupOutcome::Started(InferenceGroup::new(child,events),())
            },
            Err(_) => StartupOutcome::Uncertain(()),
        }
    });
    let (events, child) = engine.spawn().unwrap();
    let engine_job = child.owned_job().expect("assigned engine job");
    let wire = Wire::new(generation, capability).unwrap();
    let mut s = Supervisor::new(ShellDriver::new(ShellChannel::new(Transport::new(wire),child),events),factory);
    tick_until(&mut s, |s| s.ready());
    assert!(engine_job.active_processes().unwrap() >= 1);

    // Native report grant shares the actual Python lane and owns the writer.
    let ticket = reserve(&mut s, SaveKind::Report);
    let path = root.clone();
    let (report_tx, report_rx) = mpsc::channel();
    let report_waiter = thread::spawn(move || {
        let result = ticket.wait_grant().unwrap().submit(Box::new(move |entered| {
            mark(&path,"report-entered");
            wait_file(&path,"report-return")?;
            *entered = true;
            write_verified_report(&path.join("synthetic.pdf"),"pdf",b"%PDF-1.7\n%%EOF")
        })).unwrap().recv().unwrap();
        report_tx.send(result).unwrap();
    });
    tick_until(&mut s, |_| root.join("report-entered").is_file());
    mark(&root,"report-probe");
    tick_until(&mut s, |_| root.join("report-probe-confirmed").is_file());
    assert!(report_rx.try_recv().is_err());
    assert!(s.reserve_save(SaveKind::Export).is_err());
    assert_eq!(launches.load(Ordering::Acquire),0);
    mark(&root,"report-return");
    tick_until(&mut s, |_| report_waiter.is_finished());
    report_waiter.join().unwrap();
    assert_eq!(report_rx.recv().unwrap().unwrap().status,"saved");
    assert_eq!(fs::read(root.join("synthetic.pdf")).unwrap(),b"%PDF-1.7\n%%EOF");

    // Actual demand/grant with actual Windows job and a live descendant.
    mark(&root,"request-demand");
    tick_until(&mut s, |_| root.join("callback-entered").is_file());
    assert_eq!(launches.load(Ordering::Acquire),1);
    assert!(observed_job.lock().unwrap().as_ref().unwrap().active_processes().unwrap() >= 2);
    assert!(s.reserve_save(SaveKind::Report).is_err());
    mark(&root,"callback-return");
    tick_until(&mut s, |_| root.join("demand-complete").is_file());
    assert_eq!(observed_job.lock().unwrap().as_ref().unwrap().active_processes().unwrap(),0);
    println!("C1-C2-INFERENCE-GROUP-ZERO: retained owned job observed empty after release");

    // STOP cannot certify a closed engine while a native writer is active.
    let ticket = reserve(&mut s, SaveKind::Export);
    let path = root.clone();
    let (export_tx, export_rx) = mpsc::channel();
    let export_waiter = thread::spawn(move || {
        let result = ticket.wait_grant().unwrap().submit(Box::new(move |_| {
            mark(&path,"export-entered");
            wait_file(&path,"export-return")?;
            Ok(NativeReportSave {status:"cancelled",filename:None})
        })).unwrap().recv().unwrap();
        export_tx.send(result).unwrap();
    });
    tick_until(&mut s, |_| root.join("export-entered").is_file());
    mark(&root,"export-probe");
    tick_until(&mut s, |_| root.join("export-probe-confirmed").is_file());
    s.request_stop();
    tick_until(&mut s, |_| root.join("stop-seen").is_file());
    assert!(!s.closed());
    assert!(export_rx.try_recv().is_err());
    mark(&root,"export-return");
    tick_until(&mut s, |s| s.closed());
    export_waiter.join().unwrap();
    assert_eq!(export_rx.recv().unwrap().unwrap().status,"cancelled");
    assert!(root.join("engine-settled").is_file());
    assert_eq!(engine_job.active_processes().unwrap(),0);
    assert_eq!(launches.load(Ordering::Acquire),1);
    println!("C1-C2-ACTUAL-OWNED-HOST-PASS: real pipes; real job descendant and zero; shared lane; joined saves; graceful STOP");
    // Keep synthetic markers for local runner evidence; no artifact upload.
}
