"""Pure owned host protocol fixtures; no process, pipe, socket or model."""
import pytest

from backend.resource_admission import Coordinator,GIB,Operation
from backend.resource_host import HostBroker,FrameReader,ProtocolFault,MAX_FRAME,LEGACY_STOP

GEN="a"*32
KEY="b"*64

def setup(memory=3*GIB):
    c=Coordinator(lambda:"adaptive",lambda:memory)
    return c,HostBroker(c,GEN,KEY)

def frame(seq,command,*,gen=GEN,key=KEY):
    return f"POD1 {gen} {key} {seq} {command}\n".encode()

def exchange(b,chunk):
    replies=b.receive(chunk)
    for reply in replies:
        b.reply_written(reply)
    return replies

def grant(b,seq=1):
    reply=exchange(b,frame(seq,"GRANT_REQUEST LOCAL_INFERENCE"))[0].decode().split()
    assert reply[:5]==["POD1",GEN,str(seq),"GRANT_REPLY","GRANTED"]
    return reply[5]

def test_grant_holds_lane_until_exact_host_release():
    c,b=setup()
    gid=grant(b)
    assert len(gid)==32 and c.status()["phase"]=="running"
    assert c.try_acquire(Operation.DATA).code=="resource_busy"
    assert exchange(b,frame(2,"GRANT_REQUEST LOCAL_INFERENCE"))[0].endswith(b"DENIED resource_busy\n")
    assert exchange(b,frame(3,"DRAIN "+gid))[0].endswith(("DRAINING "+gid+"\n").encode())
    assert c.status()["phase"]=="draining"
    assert c.try_acquire(Operation.TRAINING).code=="resource_busy"
    assert exchange(b,frame(4,"RELEASE "+gid+" EXITED"))[0].endswith(("RELEASED "+gid+"\n").encode())
    assert not c.status()["active"]
    assert grant(b,5)!=gid

def test_data_lane_and_low_memory_refusals_do_not_reserve_host():
    c,b=setup()
    lease=c.try_acquire(Operation.DATA).lease
    assert c.start(lease)
    assert exchange(b,frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))[0].endswith(b"DENIED resource_busy\n")
    assert c.release(lease)
    grant(b,2)
    c,b=setup(GIB)
    assert exchange(b,frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))[0].endswith(b"DENIED low_memory_headroom\n")
    assert not c.status()["active"]

def test_split_frame_and_sequential_replies():
    c,b=setup()
    raw=frame(1,"GRANT_REQUEST LOCAL_INFERENCE")
    for byte in raw[:-1]:
        assert exchange(b,bytes([byte]))==[]
    replies=exchange(b,raw[-1:])
    assert len(replies)==1 and b"GRANTED" in replies[0]
    assert b"DENIED resource_busy" in exchange(b,frame(2,"GRANT_REQUEST LOCAL_INFERENCE"))[0]

@pytest.mark.parametrize("bad",[
    frame(2,"GRANT_REQUEST LOCAL_INFERENCE"),
    frame(1,"GRANT_REQUEST LOCAL_INFERENCE",gen="c"*32),
    frame(1,"GRANT_REQUEST LOCAL_INFERENCE",key="c"*64),
    frame(1,"GRANT_REQUEST LOCAL_INFERENCE extra"),
    frame(1,"RELEASE "+"c"*32+" EXITED"),
    frame(1,"UNKNOWN"),
    frame("01","STOP"),
    frame(2147483648,"STOP"),
    b"POD1\x00\n",
    b"\n",
])
def test_malformed_or_stale_frame_fails_closed(bad):
    c,b=setup()
    with pytest.raises(ProtocolFault,match="protocol fault"):
        exchange(b,bad)
    assert c.status()["stopping"]
    with pytest.raises(ProtocolFault):
        exchange(b,frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))

def test_duplicate_sequence_blocks_outstanding_lease():
    c,b=setup()
    grant(b)
    with pytest.raises(ProtocolFault):
        exchange(b,frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))
    assert c.status()["phase"]=="blocked"
    assert c.status()["stopping"]

def test_wrong_grant_cannot_release():
    c,b=setup()
    gid=grant(b)
    wrong=("0" if gid[0]!="0" else "1")+gid[1:]
    with pytest.raises(ProtocolFault):
        exchange(b,frame(2,"RELEASE "+wrong+" EXITED"))
    assert c.status()["phase"]=="blocked"

def test_legacy_stop_preserves_grant_and_allows_exact_exit():
    c,b=setup()
    gid=grant(b)
    assert exchange(b,LEGACY_STOP)==[]
    assert c.status()["stopping"] and c.status()["phase"]=="draining"
    assert exchange(b,frame(2,"GRANT_REQUEST LOCAL_INFERENCE"))[0].endswith(b"DENIED shutting_down\n")
    exchange(b,frame(3,"RELEASE "+gid+" EXITED"))
    assert not c.status()["active"] and c.status()["stopping"]

def test_versioned_stop_and_never_started_release():
    c,b=setup()
    gid=grant(b)
    assert exchange(b,frame(2,"STOP"))[0].endswith(b"ADMISSION_STOPPED\n")
    assert c.status()["active"]
    exchange(b,frame(3,"RELEASE "+gid+" NEVER_STARTED"))
    assert not c.status()["active"] and c.status()["stopping"]

def test_lost_reply_or_eof_blocks_and_never_retries():
    c,b=setup()
    grant(b)
    b.transport_lost()
    b.transport_lost()
    assert c.status()["phase"]=="blocked"
    with pytest.raises(ProtocolFault):
        exchange(b,frame(2,"STOP"))

def test_fault_does_not_block_unrelated_data_owner():
    c,b=setup()
    lease=c.try_acquire(Operation.DATA).lease
    assert c.start(lease)
    b.transport_lost()
    assert c.status()["phase"]=="running"
    assert c.release(lease)
    assert c.status()["stopping"]

def test_frame_reader_exact_cap_and_overflow():
    reader=FrameReader()
    assert reader.feed(b"x"*(MAX_FRAME-1))==[]
    assert reader.feed(b"\n")==[b"x"*(MAX_FRAME-1)+b"\n"]
    with pytest.raises(ProtocolFault):
        reader.feed(b"x"*MAX_FRAME)
    with pytest.raises(ProtocolFault):
        reader.feed(b"\n")

def test_frame_chunk_cap_and_non_ascii():
    for chunk in (b"x"*(MAX_FRAME+1),b"\xff\n",b"\r\n",b""):
        with pytest.raises(ProtocolFault):
            FrameReader().feed(chunk)

def test_capability_not_returned_or_in_fault_message():
    c,b=setup()
    reply=exchange(b,frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))[0]
    assert KEY.encode() not in reply
    with pytest.raises(ProtocolFault) as exc:
        exchange(b,frame(2,"RELEASE "+"c"*32+" INVALID"))
    assert KEY not in str(exc.value)


@pytest.mark.parametrize("suffix",[frame(2,"STOP"),frame(2,"STOP")[:7]])
def test_pipelined_request_rejected_before_dispatch(suffix):
    c,b=setup()
    with pytest.raises(ProtocolFault):
        b.receive(frame(1,"GRANT_REQUEST LOCAL_INFERENCE")+suffix)
    assert not c.status()["active"] and c.status()["stopping"]


def test_next_read_before_reply_flush_blocks_grant():
    c,b=setup()
    reply=b.receive(frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))[0]
    assert b"GRANTED" in reply
    with pytest.raises(ProtocolFault):
        b.receive(frame(2,"STOP")[:1])
    assert c.status()["phase"]=="blocked"


def test_release_holds_lane_through_reply_write():
    c,b=setup()
    gid=grant(b)
    reply=b.receive(frame(2,"RELEASE "+gid+" EXITED"))[0]
    assert b"RELEASED" in reply
    assert c.try_acquire(Operation.DATA).code=="resource_busy"
    b.reply_written(reply)
    assert not c.status()["active"]


def test_release_write_failure_blocks():
    c,b=setup()
    gid=grant(b)
    b.receive(frame(2,"RELEASE "+gid+" EXITED"))
    b.transport_lost()
    assert c.status()["phase"]=="blocked"


def test_wrong_reply_ack_blocks():
    c,b=setup()
    reply=b.receive(frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))[0]
    with pytest.raises(ProtocolFault):
        b.reply_written(reply+b" ")
    assert c.status()["phase"]=="blocked"


def test_duplicate_reply_ack_fails_closed():
    c,b=setup()
    reply=b.receive(frame(1,"GRANT_REQUEST LOCAL_INFERENCE"))[0]
    b.reply_written(reply)
    with pytest.raises(ProtocolFault):
        b.reply_written(reply)
    assert c.status()["phase"]=="blocked"


def test_owned_pump_split_stop_release_and_eof():
    from backend.resource_host import serve_owned
    c,b=setup()
    replies=[]
    pending=[frame(1,"GRANT_REQUEST LOCAL_INFERENCE")[:12],
             frame(1,"GRANT_REQUEST LOCAL_INFERENCE")[12:],
             frame(2,"STOP")]
    def read(cap):
        assert cap==MAX_FRAME
        if pending:
            return pending.pop(0)
        if len(replies)==2:
            gid=replies[0].decode().split()[-1]
            return frame(3,"RELEASE "+gid+" EXITED")
        return b""
    def write(reply):
        replies.append(reply)
        assert c.status()["active"]
        return len(reply)
    def flush():
        assert c.status()["active"]
    with pytest.raises(ProtocolFault):
        serve_owned(b,read,write,flush)
    assert len(replies)==3
    assert b"GRANTED" in replies[0]
    assert b"ADMISSION_STOPPED" in replies[1]
    assert b"RELEASED" in replies[2]
    assert not c.status()["active"] and c.status()["stopping"]


@pytest.mark.parametrize("fault",["short","none","bool","write","flush"])
def test_owned_pump_failed_release_delivery_retains_grant(fault):
    from backend.resource_host import serve_owned
    c,b=setup()
    gid=grant(b)
    def read(cap):
        return frame(2,"RELEASE "+gid+" EXITED")
    def write(reply):
        if fault=="short":
            return len(reply)-1
        if fault=="none":
            return None
        if fault=="bool":
            return True
        if fault=="write":
            raise OSError("secret "+KEY)
        return len(reply)
    def flush():
        if fault=="flush":
            raise OSError("secret "+KEY)
        pytest.fail("Invalid write must not flush")
    with pytest.raises(ProtocolFault) as err:
        serve_owned(b,read,write,flush)
    assert KEY not in str(err.value)
    assert c.status()["phase"]=="blocked" and c.status()["stopping"]


@pytest.mark.parametrize("chunk",[b"",b"x"*(MAX_FRAME+1),None])
def test_owned_pump_invalid_read_fails_closed(chunk):
    from backend.resource_host import serve_owned
    c,b=setup()
    grant(b)
    with pytest.raises(ProtocolFault):
        serve_owned(b,lambda _:chunk,lambda _:pytest.fail("write"),lambda:pytest.fail("flush"))
    assert c.status()["phase"]=="blocked"


def test_owned_pump_partial_eof_never_dispatches():
    from backend.resource_host import serve_owned
    c,b=setup()
    chunks=iter([frame(1,"GRANT_REQUEST LOCAL_INFERENCE")[:-1],b""])
    with pytest.raises(ProtocolFault):
        serve_owned(b,lambda _:next(chunks),lambda _:pytest.fail("write"),lambda:pytest.fail("flush"))
    assert not c.status()["active"] and c.status()["stopping"]


def test_owned_pump_read_exception_sanitized():
    from backend.resource_host import serve_owned
    c,b=setup()
    grant(b)
    def read(_):
        raise OSError(KEY)
    with pytest.raises(ProtocolFault) as err:
        serve_owned(b,read,lambda _:pytest.fail("write"),lambda:pytest.fail("flush"))
    assert KEY not in str(err.value)
    assert c.status()["phase"]=="blocked"


class _Descriptor:
    def __init__(self, fd):
        self.fd = fd

    def fileno(self):
        return self.fd


class _FixtureDescriptors:
    """Inert call recorder; never touches process-global descriptors."""
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail
        self.chunks = []
        self.replies = []

    def _record(self, name, *args):
        self.calls.append((name,*args))
        if self.fail == name:
            raise OSError(KEY)

    def dup(self, fd):
        self._record("dup",fd)
        return 9

    def set_inheritable(self, fd, value):
        self._record("set_inheritable",fd,value)

    def get_inheritable(self, fd):
        self._record("get_inheritable",fd)
        return self.fail == "inherited"

    def dup2(self, src, dst, *, inheritable):
        self._record("dup2",src,dst,inheritable)

    def binary(self, fd):
        self._record("binary",fd)

    def native(self, fd):
        self._record("native",fd)

    def write(self, fd, payload):
        self._record("write",fd,payload)
        self.replies.append(payload)
        return len(payload)

    def read(self, fd, cap):
        self._record("read",fd,cap)
        return self.chunks.pop(0) if self.chunks else b""

    def close(self, fd):
        self._record("close",fd)


def _prepare_fixture(ops, fds=(0,1,2)):
    from backend.resource_host import prepare_control_stdio
    return prepare_control_stdio(*map(_Descriptor,fds),ops=ops,binary_mode=ops.binary,
                                 native_redirect=ops.native)


def test_control_stdio_isolates_only_owned_standard_descriptors():
    ops=_FixtureDescriptors()
    fd,writer=_prepare_fixture(ops)
    assert fd==0
    assert ops.calls==[("dup",1),("set_inheritable",9,False),
                       ("get_inheritable",9),("dup2",2,1,False),("native",1),
                       ("binary",0),("binary",9)]
    assert writer.write(b"POD1")==4
    writer.flush()
    writer.close()
    writer.close()
    assert ops.calls[-2:]==[("write",9,b"POD1"),("close",9)]


@pytest.mark.parametrize("fds",[(0,4,2),(1,1,2),(0,True,2),(0,1,0)])
def test_control_stdio_refuses_unexpected_descriptors_before_mutation(fds):
    ops=_FixtureDescriptors()
    with pytest.raises(ProtocolFault):
        _prepare_fixture(ops,fds)
    assert ops.calls==[]


@pytest.mark.parametrize("stage",["set_inheritable","get_inheritable","inherited","dup2","binary","native"])
def test_control_stdio_failure_closes_only_private_duplicate(stage):
    ops=_FixtureDescriptors(stage)
    with pytest.raises(ProtocolFault) as exc:
        _prepare_fixture(ops)
    assert KEY not in str(exc.value)
    assert ops.calls[-1]==("close",9)
    assert [call for call in ops.calls if call[0]=="close"]==[("close",9)]


def test_control_stdio_failed_dup_never_closes_standard_descriptors():
    ops=_FixtureDescriptors("dup")
    with pytest.raises(ProtocolFault):
        _prepare_fixture(ops)
    assert ops.calls==[("dup",1)]


def _bootstrap(ops, env):
    from backend.resource_host import prepare_owned_control
    return prepare_owned_control(env,*map(_Descriptor,(0,1,2)),ops=ops,
                                 binary_mode=ops.binary,native_redirect=ops.native)


def _control_env():
    return {"PILOTODIN_DESKTOP_WATCH_STDIN":"1",
            "PILOTODIN_CONTROL_GENERATION":GEN,
            "PILOTODIN_CONTROL_CAPABILITY":KEY}


@pytest.mark.parametrize("missing",["PILOTODIN_CONTROL_GENERATION",
                                    "PILOTODIN_CONTROL_CAPABILITY",
                                    "PILOTODIN_DESKTOP_WATCH_STDIN"])
def test_bootstrap_refuses_partial_environment_and_consumes_secrets(missing):
    ops=_FixtureDescriptors()
    env=_control_env()
    del env[missing]
    with pytest.raises(ProtocolFault):
        _bootstrap(ops,env)
    assert ops.calls==[]
    assert "PILOTODIN_CONTROL_GENERATION" not in env
    assert "PILOTODIN_CONTROL_CAPABILITY" not in env


def test_bootstrap_discard_single_use_closes_only_private_writer():
    ops=_FixtureDescriptors()
    env=_control_env()
    boot=_bootstrap(ops,env)
    assert env=={"PILOTODIN_DESKTOP_WATCH_STDIN":"1"}
    boot.discard_unstarted()
    assert ops.calls[-1]==("close",9)
    with pytest.raises(ProtocolFault):
        boot.discard_unstarted()
    with pytest.raises(ProtocolFault):
        boot.run(setup()[0],lambda:pytest.fail("Reused bootstrap"))
    assert ops.calls.count(("close",9))==1


def test_bootstrap_runs_owned_stream_and_notifies_stop_once():
    ops=_FixtureDescriptors()
    ops.chunks=[frame(1,"STOP"),b""]
    boot=_bootstrap(ops,_control_env())
    c,_=setup()
    notified=[]
    with pytest.raises(ProtocolFault):
        boot.run(c,lambda:notified.append(c.status()))
    assert len(notified)==1 and notified[0]["stopping"]
    assert ops.replies[0].endswith(b"ADMISSION_STOPPED\n")
    assert ops.calls[-1]==("close",9)


def test_stop_notification_waits_for_exact_release_reply():
    from backend.resource_host import serve_owned
    c,b=setup()
    gid=grant(b)
    pending=iter([frame(2,"STOP"),frame(3,"RELEASE "+gid+" EXITED"),b""])
    notifications=[]
    replies=[]
    def write(reply):
        assert not notifications
        replies.append(reply)
        return len(reply)
    def notify():
        assert len(replies)==2 and not c.status()["active"]
        notifications.append(True)
    with pytest.raises(ProtocolFault):
        serve_owned(b,lambda _:next(pending),write,lambda:None,on_shutdown=notify)
    assert notifications==[True]


def test_transport_fault_notifies_shutdown_without_releasing_grant():
    from backend.resource_host import serve_owned
    c,b=setup()
    grant(b)
    notifications=[]
    with pytest.raises(ProtocolFault):
        serve_owned(b,lambda _:b"",lambda _:pytest.fail("write"),lambda:None,
                    on_shutdown=lambda:notifications.append(c.status()))
    assert len(notifications)==1 and notifications[0]["phase"]=="blocked"


def test_control_writer_close_error_not_retried():
    ops=_FixtureDescriptors("close")
    _,writer=_prepare_fixture(ops)
    with pytest.raises(OSError):
        writer.close()
    writer.close()
    assert ops.calls.count(("close",9))==1
    with pytest.raises(ProtocolFault):
        writer.write(b"POD1")
