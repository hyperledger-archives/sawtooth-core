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
    "debug" : {
      "class" : "logging.FileHandler",
      "level" : "DEBUG",
      "formatter" : "simple",
      "filename" : "override"
    },

    "error" : {
      "class" : "logging.FileHandler",
      "level" : "ERROR",
      "formatter" : "simple",
      "filename" : "override"
    }
  },

  "root": {
    "level" : "INFO",
    "handlers" : ["debug", "error"]
  }
}
