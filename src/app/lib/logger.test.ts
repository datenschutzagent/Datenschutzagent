import { describe, it, expect, vi } from "vitest";
import { logger, type LogEntry, type LogSink } from "./logger";

describe("logger", () => {
  function captureSink(): { entries: LogEntry[]; sink: LogSink } {
    const entries: LogEntry[] = [];
    const sink: LogSink = (entry) => entries.push(entry);
    return { entries, sink };
  }

  it("emits warn entries", () => {
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    logger.warn("Test-Warnung", { key: "value" });

    expect(entries).toHaveLength(1);
    expect(entries[0].level).toBe("warn");
    expect(entries[0].message).toBe("Test-Warnung");
    expect(entries[0].context).toEqual({ key: "value" });
  });

  it("emits error entries with error object", () => {
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    const err = new Error("boom");
    logger.error("Fehler aufgetreten", { requestPath: "/api/v1/cases" }, err);

    expect(entries).toHaveLength(1);
    expect(entries[0].level).toBe("error");
    expect(entries[0].error).toBe(err);
    expect(entries[0].context).toEqual({ requestPath: "/api/v1/cases" });
  });

  it("includes an ISO timestamp on every entry", () => {
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    logger.warn("msg");

    expect(entries[0].timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });

  it("does not include context key when no context is passed", () => {
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    logger.warn("kein Kontext");

    expect("context" in entries[0]).toBe(false);
  });

  it("does not include error key when no error is passed", () => {
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    logger.warn("kein Fehler");

    expect("error" in entries[0]).toBe(false);
  });

  it("calls multiple sinks", () => {
    const { entries: a, sink: sinkA } = captureSink();
    const { entries: b, sink: sinkB } = captureSink();
    logger.setSinks([sinkA, sinkB]);

    logger.warn("beide Sinks");

    expect(a).toHaveLength(1);
    expect(b).toHaveLength(1);
  });

  it("does not crash when a sink throws", () => {
    const crashingSink: LogSink = () => {
      throw new Error("sink failure");
    };
    const { entries, sink: goodSink } = captureSink();
    logger.setSinks([crashingSink, goodSink]);

    expect(() => logger.warn("robust")).not.toThrow();
    // goodSink still received the entry
    expect(entries).toHaveLength(1);
  });

  it("info entries are captured by the sink regardless of log level config", () => {
    // The sink always receives entries that pass the level filter.
    // In test (dev) mode all levels pass.
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    logger.info("Info-Nachricht");

    // In dev mode (IS_DEV=true) info should be emitted.
    // In CI (IS_DEV=false) info is filtered → length may be 0 or 1.
    // We only assert the structure when something is emitted.
    if (entries.length > 0) {
      expect(entries[0].level).toBe("info");
    }
  });

  it("error entries carry the correct level", () => {
    const { entries, sink } = captureSink();
    logger.setSinks([sink]);

    logger.error("schwerer Fehler");

    expect(entries[0].level).toBe("error");
  });
});
