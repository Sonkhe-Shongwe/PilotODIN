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
