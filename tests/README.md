# FanzinesEditor tests

Two tiers. Run them from the FanzinesEditor folder.

| | When | How long | What it touches |
|---|---|---|---|
| **Tier 1** | after every change | about 10 seconds | nothing: a fake FTP server in memory and a temporary folder |
| **Tier 2** | before building an exe for Edie, or after changing FTP-level code | about 5 minutes | the real test root, `/fanzines-test` (never `/fanzines`), put back afterwards |

```
venv12\Scripts\python.exe tests\tier1.py
venv12\Scripts\python.exe tests\tier2.py
```

Each prints PASS/FAIL lines, writes them to `tests\results\tier1.txt` / `tier2.txt` as it goes (so an interrupted
run still leaves its results), and exits with 0 only if everything passed.

## The files

- `harness.py` -- the shared setup. It makes sure that no window or dialog ever appears (dialogs are answered from a
  script), pins the settings that matter in memory (Test mode on, the test root, no local-directory root path) and
  refuses to let a test save a settings file, uses a temporary copy of the server-to-local table, and sends logs to a
  temporary folder. Tier 2 refuses to start unless `FanzinesEditor settings.txt` says `Test mode=True` and
  `Test Root directory=fanzines-test`.
- `fakeftp.py` -- the fake FTP server. It stands in for the ftplib connection FE's FTP class uses, so all of FE's own
  code, including its FTP code, runs unchanged. Tests can make particular operations fail
  (`server.Fail("stor", lambda path: path.endswith("/x.pdf"))`).
- `tier1.py`, `tier2.py` -- the tests.
- `fixtures/` -- real fanzine index pages (Apollo, Innuendo, Australian SF News) that Tier 1 serves from its fake server.

## Adding a test

Put most new tests in Tier 1: anything about what FE does with pages, rows, files, PDFs, or the Classic list can be
checked against the fake server, including what happens when the server fails. Add to Tier 2 only what needs the real
server.
