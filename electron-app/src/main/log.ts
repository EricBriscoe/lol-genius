import log from "electron-log/main";

log.transports.file.level = "info";
log.transports.console.level = "debug";
log.transports.file.format = "{y}-{m}-{d} {h}:{i}:{s} [{level}] {scope}: {text}";

export default log;
