"""Pure exact Noble security transaction predicate; never invokes APT."""
import re

OLD = '2.42-4ubuntu2.10'
VERSION = '2.42-4ubuntu2.11'
NAMES = ('binutils', 'binutils-common', 'binutils-x86-64-linux-gnu', 'libbinutils',
         'libctf0', 'libctf-nobfd0', 'libgprofng0', 'libsframe1')
ORIGIN = r' Ubuntu:24\.04/noble-security \[amd64\]'
INST = re.compile(r'Inst ([a-z0-9-]+)(?::amd64)? \[([^\]]+)\] \(([^ ]+)' + ORIGIN
                  + r'\)(?: \[(?:binutils:amd64 )?\])?')
CONF = re.compile(r'Conf ([a-z0-9-]+)(?::amd64)? \(([^ ]+)' + ORIGIN + r'\)')
SUMMARY = re.compile(r'(\d+) upgraded, (\d+) newly installed, (\d+) to remove and \d+ not upgraded\.')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def exact_plan(stdout, installed):
    need(set(installed) == set(NAMES) and all(v in (OLD, VERSION) for v in installed.values()), 'INSTALLED_SET')
    expected = {n for n in NAMES if installed[n] == OLD}
    lines = stdout.splitlines()
    summaries = [SUMMARY.fullmatch(line) for line in lines if SUMMARY.fullmatch(line)]
    need(len(summaries) == 1 and tuple(map(int, summaries[0].groups())) == (len(expected), 0, 0), 'APT_SUMMARY')
    actions = [line for line in lines if re.match(r'^(?:Inst|Conf|Remv|Purg)(?:\s|$)', line)]
    seen, configured = set(), set()
    for line in actions:
        m = INST.fullmatch(line)
        if m:
            n, old, new = m.groups()
            need(n in expected and n not in seen and old == OLD and new == VERSION, 'APT_UNEXPECTED_INSTALL')
            seen.add(n)
        else:
            m = CONF.fullmatch(line)
            need(m and m[1] in seen and m[1] not in configured and m[2] == VERSION, 'APT_UNEXPECTED_ACTION')
            configured.add(m[1])
    need(seen == expected and configured == expected, 'APT_INCOMPLETE_TRANSACTION')
    return actions
