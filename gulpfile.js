const gulp = require('gulp')
const uglify = require('gulp-uglify')
const del = require('del')
const sass = require('gulp-sass')
const filelog = require('gulp-filelog')
const include = require('gulp-include')
const sourcemaps = require('gulp-sourcemaps')
const path = require('path')

// Paths
let environment
const repoRoot = path.join(__dirname)
const npmRoot = path.join(repoRoot, 'node_modules')
const govukToolkitRoot = path.join(npmRoot, 'govuk_frontend_toolkit')
const govukElementsRoot = path.join(npmRoot, 'govuk-elements-sass')
const govukFrontendRoot = path.join(npmRoot, 'digitalmarketplace-govuk-frontend', 'govuk-frontend')
const dmToolkitRoot = path.join(npmRoot, 'digitalmarketplace-frontend-toolkit', 'toolkit')
const assetsFolder = path.join(repoRoot, 'app', 'assets')
const staticFolder = path.join(repoRoot, 'app', 'static')
const govukTemplateFolder = path.join(repoRoot, 'node_modules', 'govuk_template')
const govukTemplateAssetsFolder = path.join(govukTemplateFolder, 'assets')
const govukTemplateLayoutsFolder = path.join(govukTemplateFolder, 'views', 'layouts')
const govukFrontendFontsFolder = path.join(govukFrontendRoot, 'assets', 'fonts')
const govukFrontendImageFolder = path.join(govukFrontendRoot, 'assets', 'images')

// JavaScript paths
const jsSourceFile = path.join(assetsFolder, 'javascripts', 'application.js')
const jsDistributionFolder = path.join(staticFolder, 'javascripts')
const jsDistributionFile = 'application.js'

// CSS paths
const cssSourceGlob = path.join(assetsFolder, 'scss', 'application*.scss')
const cssDistributionFolder = path.join(staticFolder, 'stylesheets')

// Configuration
const sassOptions = {
  development: {
    outputStyle: 'expanded',
    lineNumbers: true,
    includePaths: [
      assetsFolder + '/scss',
      dmToolkitRoot + '/scss',
      govukToolkitRoot + '/stylesheets',
      govukElementsRoot + '/public/sass'
    ],
    sourceComments: true,
    errLogToConsole: true
  },
  production: {
    outputStyle: 'compressed',
    lineNumbers: true,
    includePaths: [
      assetsFolder + '/scss',
      dmToolkitRoot + '/scss',
      govukToolkitRoot + '/stylesheets',
      govukElementsRoot + '/public/sass'
    ]
  }
}

const uglifyOptions = {
  development: {
    mangle: false,
    output: {
      beautify: true,
      semicolons: true,
      comments: true,
      indent_level: 2
    },
    compress: false
  },
  production: {
    mangle: true
  }
}

const logErrorAndExit = function logErrorAndExit (err) {
  // coloured text: https://coderwall.com/p/yphywg/printing-colorful-text-in-terminal-when-run-node-js-script
  console.log('\x1b[41m\x1b[37m  Error: ' + err.message + '\x1b[0m')
  process.exit(1)
}

gulp.task('clean:js', function () {
  return del(jsDistributionFolder + '/**/*').then(function (paths) {
    console.log('💥  Deleted the following JavaScript files:\n', paths.join('\n'))
  })
})

gulp.task('clean:css', function () {
  return del(cssDistributionFolder + '/**/*').then(function (paths) {
    console.log('💥  Deleted the following CSS files:\n', paths.join('\n'))
  })
})

gulp.task('clean', gulp.parallel('clean:js', 'clean:css'))

gulp.task('sass', function () {
  const stream = gulp.src(cssSourceGlob)
    .pipe(filelog('Compressing SCSS files'))
    .pipe(
      sass(sassOptions[environment]))
    .on('error', logErrorAndExit)
    .pipe(gulp.dest(cssDistributionFolder))

  stream.on('end', function () {
    console.log('💾  Compressed CSS saved as .css files in ' + cssDistributionFolder)
  })

  return stream
})

gulp.task('js', function () {
  const stream = gulp.src(jsSourceFile)
    .pipe(filelog('Compressing JavaScript files'))
    .pipe(include({ hardFail: true }))
    .pipe(sourcemaps.init())
    .pipe(uglify(
      uglifyOptions[environment]
    ))
    .pipe(sourcemaps.write('./maps'))
    .pipe(gulp.dest(jsDistributionFolder))

  stream.on('end', function () {
    console.log('💾 Compressed JavaScript saved as ' + jsDistributionFolder + '/' + jsDistributionFile)
  })

  return stream
})

function copyFactory (resourceName, sourceFolder, targetFolder) {
  return function () {
    return gulp
      .src(sourceFolder + '/**/*', { base: sourceFolder })
      .pipe(gulp.dest(targetFolder))
      .on('end', function () {
        console.log('📂  Copied ' + resourceName)
      })
  }
}

gulp.task(
  'copy:template_assets:stylesheets',
  copyFactory(
    'GOV.UK template stylesheets',
    govukTemplateAssetsFolder + '/stylesheets',
    staticFolder + '/stylesheets'
  )
)

gulp.task(
  'copy:template_assets:images',
  copyFactory(
    'GOV.UK template images',
    govukTemplateAssetsFolder + '/images',
    staticFolder + '/images'
  )
)

gulp.task(
  'copy:template_assets:javascripts',
  copyFactory(
    'GOV.UK template Javascript files',
    govukTemplateAssetsFolder + '/javascripts',
    staticFolder + '/javascripts'
  )
)

gulp.task(
  'copy:dm_toolkit_assets:stylesheets',
  copyFactory(
    'stylesheets from the Digital Marketplace frontend toolkit',
    dmToolkitRoot + '/scss',
    'app/assets/scss/toolkit'
  )
)

gulp.task(
  'copy:dm_toolkit_assets:images',
  copyFactory(
    'images from the Digital Marketplace frontend toolkit',
    dmToolkitRoot + '/images',
    staticFolder + '/images'
  )
)

gulp.task(
  'copy:govuk_toolkit_assets:images',
  copyFactory(
    'images from the GOVUK frontend toolkit',
    govukToolkitRoot + '/images',
    staticFolder + '/images'
  )
)

gulp.task(
  'copy:dm_toolkit_assets:templates',
  copyFactory(
    'templates from the Digital Marketplace frontend toolkit',
    dmToolkitRoot + '/templates',
    'app/templates/toolkit'
  )
)

gulp.task(
  'copy:images',
  copyFactory(
    'image assets from app to static folder',
    assetsFolder + '/images',
    staticFolder + '/images'
  )
)

gulp.task(
  'copy:svg',
  copyFactory(
    'image assets from app to static folder',
    assetsFolder + '/svg',
    staticFolder + '/svg'
  )
)

gulp.task(
  'copy:govuk_template',
  copyFactory(
    'GOV.UK template into app folder',
    govukTemplateLayoutsFolder,
    'app/templates/govuk'
  )
)

gulp.task(
  'copy:govuk_frontend_assets:fonts',
  copyFactory(
    'fonts from the GOVUK frontend assets',
    govukFrontendFontsFolder,
    staticFolder + '/fonts'
  )
)

gulp.task(
  'copy:govuk_frontend_assets:images',
  copyFactory(
    'images from the GOVUK frontend',
    govukFrontendImageFolder,
    staticFolder + '/images/govuk-frontend/'
  )
)

gulp.task('set_environment_to_development', function (cb) {
  environment = 'development'
  cb()
})

gulp.task('set_environment_to_production', function (cb) {
  environment = 'production'
  cb()
})

gulp.task('copy', gulp.parallel(
  'copy:template_assets:images',
  'copy:template_assets:stylesheets',
  'copy:template_assets:javascripts',
  'copy:govuk_toolkit_assets:images',
  'copy:dm_toolkit_assets:stylesheets',
  'copy:dm_toolkit_assets:images',
  'copy:dm_toolkit_assets:templates',
  'copy:images',
  'copy:svg',
  'copy:govuk_template',
  'copy:govuk_frontend_assets:fonts',
  'copy:govuk_frontend_assets:images'
))

gulp.task('compile', gulp.series('copy', gulp.parallel('sass', 'js')))

gulp.task('build:development', gulp.series(gulp.parallel('set_environment_to_development', 'clean'), 'compile'))

gulp.task('build:production', gulp.series(gulp.parallel('set_environment_to_production', 'clean'), 'compile'))

gulp.task('watch', gulp.series('build:development', function () {
  const jsWatcher = gulp.watch([assetsFolder + '/**/*.js'], gulp.series('js'))
  const cssWatcher = gulp.watch([assetsFolder + '/**/*.scss'], gulp.series('sass'))
  const dmWatcher = gulp.watch([npmRoot + '/digitalmarketplace-frameworks/**'], gulp.series('copy:frameworks'))
  const notice = function (event) {
    console.log('File ' + event.path + ' was ' + event.type + ' running tasks...')
  }

  cssWatcher.on('change', notice)
  jsWatcher.on('change', notice)
  dmWatcher.on('change', notice)
}))
