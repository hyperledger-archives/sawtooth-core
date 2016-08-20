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
    "mktplace" : {
      "class" : "logging.StreamHandler",
      "level" : "WARNING",
      "formatter" : "simple",
      "stream": "ext://sys.stdout"
    }
  },

  "root": {
    "level" : "INFO",
    "handlers" : ["mktplace"]
  }
}
