$ErrorActionPreference = 'Stop'
Push-Location apps/web
try {
  npm ci --ignore-scripts
  npm test
} finally {
  Pop-Location
}
firebase deploy --only hosting --project portfolio-c1ae4
