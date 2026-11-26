import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");

function serviceWithDatabase(rows, insertError = null) {
  const supabase = {
    from(table) {
      assert.equal(table, "tracked_courses");
      let action = "select";
      let value;
      const filters = [];
      const query = {
        select() { return this; },
        order() { return this; },
        eq(column, expected) { filters.push([column, expected]); return this; },
        insert(row) { action = "insert"; value = row; return this; },
        update(row) { action = "update"; value = row; return this; },
        delete() { action = "delete"; return this; },
        async execute(single = false) {
          if (action === "insert") {
            if (insertError) return { data: null, error: insertError };
            const row = { ...value, id: `course-${rows.length + 1}` };
            rows.push(row);
            return { data: row, error: null };
          }
          const matches = rows.filter((row) => filters.every(([key, expected]) => row[key] === expected));
          if (single && matches.length !== 1) return { data: null, error: new Error("Row not found") };
          if (action === "update") Object.assign(matches[0], value);
          if (action === "delete") rows.splice(rows.indexOf(matches[0]), 1);
          return { data: single ? matches[0] : matches, error: null };
        },
        single() { return this.execute(true); },
        then(resolve, reject) { return this.execute().then(resolve, reject); },
      };
      return query;
    },
  };
  const source = readFileSync(new URL("./coursetracker.tsx", import.meta.url), "utf8");
  const javascript = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const module = { exports: {} };
  runInNewContext(javascript, {
    module, exports: module.exports,
    require(name) {
      if (name === "@/lib/supabase") return { supabase };
      throw new Error(`Unexpected import: ${name}`);
    },
  });
  return module.exports;
}

test("saved courses reload for their owner and mutations remain owner-scoped", async () => {
  const rows = [];
  const first = serviceWithDatabase(rows);
  const saved = await first.addTrackedCourse({
    profileId: "owner", title: "SQL", provider: "", status: "in_progress",
    enrolledAt: "2026-11-27", deadline: "2026-12-10", url: "https://example.com",
  });
  const reloaded = serviceWithDatabase(rows);
  const courses = await reloaded.listTrackedCourses("owner");
  assert.equal(courses.length, 1);
  assert.equal(courses[0].id, saved.id);
  assert.equal(courses[0].status, "in_progress");
  assert.equal(courses[0].deadline, "2026-12-10");
  assert.equal(courses[0].url, "https://example.com");
  assert.equal((await reloaded.listTrackedCourses("other")).length, 0);
  await assert.rejects(reloaded.deleteTrackedCourse("other", saved.id), /Row not found/);
  await reloaded.updateTrackedCourseStatus("owner", saved.id, "completed");
  assert.equal((await reloaded.listTrackedCourses("owner"))[0].status, "completed");
  await reloaded.deleteTrackedCourse("owner", saved.id);
  assert.equal((await reloaded.listTrackedCourses("owner")).length, 0);
});

test("database insert errors are propagated", async () => {
  const service = serviceWithDatabase([], new Error("Database unavailable"));
  await assert.rejects(service.addTrackedCourse({
    profileId: "owner", title: "SQL", provider: "", status: "not_started", enrolledAt: "2026-11-27",
  }), /Database unavailable/);
});

test("existing courses with nullable fields load without a provider or deadline", async () => {
  const service = serviceWithDatabase([{
    id: "existing", profile_id: "owner", title: "SQL", provider: null, url: null,
    status: "not_started", enrolled_at: "2026-11-27", deadline: null, notes: null,
  }]);
  const [course] = await service.listTrackedCourses("owner");
  assert.equal(course.provider, "");
  assert.equal(course.deadline, undefined);
  assert.equal(course.url, undefined);
});
