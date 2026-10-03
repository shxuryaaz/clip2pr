import engine
files={"a.js":"x = 1;\ny = 2;\n"}
fix=engine.Fix(bug_title="t",steps_seen=[],seen_at="0",on_screen="",expected="",root_cause="",pr_title="t",
  edits=[engine.Edit(path="a.js",find="y = 2;",replace="y = 3;")])
assert engine.apply(files,fix)=={"a.js":"x = 1;\ny = 3;\n"}
for bad in [engine.Edit(path="a.js",find="nope",replace=""), engine.Edit(path="b.js",find="x",replace="")]:
    fix.edits=[bad]
    try: engine.apply(files,fix); raise SystemExit("should fail")
    except RuntimeError: pass
print("apply ok")
