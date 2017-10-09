const path = require('path')
const webpack = require('webpack')

module.exports = {
  entry: './src/main',

  output: {
    path: path.resolve(__dirname, 'public/dist'),
    filename: 'bundle.js'
  },

  module: {
    rules: [{
      test: /\.(scss)$/,
      use: [{
        loader: 'style-loader'
      }, {
        loader: 'css-loader'
      }, {
        loader: 'postcss-loader',
        options: {
          plugins: () => [
            require('precss'),
            require('autoprefixer')
          ]
        }
      }, {
        loader: 'sass-loader'
      }]
    }]
  },

  plugins: [
    new webpack.ProvidePlugin({
      $: 'jquery',
      jQuery: 'jquery',
      'window.jQuery': 'jquery',
      Popper: ['popper.js', 'default']
    })
  ],

  devServer: {
    port: 3001,
    contentBase: path.join(__dirname, 'public'),
    publicPath: '/dist/',
    proxy: {
      '/api': 'http://localhost:3000'
    }
  }
}
