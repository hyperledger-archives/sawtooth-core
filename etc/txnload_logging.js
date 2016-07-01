{
  "version" : 1,
  "disable_existing_loggers" : false,

  "formatters": {
        "simple": {
            "format":"[%(asctime)s %(name)s %(levelname)s] %(message)s",
            "datefmt":"%H:%M:%S"
        }
    },

  "handlers" : {
    "txnload" : {
      "class" : "logging.FileHandler",
      "level" : "INFO",
      "formatter" : "simple",
      "filename" : "override"
    }
  },

  "root": {
    "level" : "INFO",
    "handlers" : ["txnload"]
  }
}
