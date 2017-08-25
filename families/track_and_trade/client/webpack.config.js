const path = require('path')

module.exports = {
  entry: './src/main',

  output: {
    path: path.resolve(__dirname, 'public/dist'),
    filename: 'bundle.js'
  }
}
