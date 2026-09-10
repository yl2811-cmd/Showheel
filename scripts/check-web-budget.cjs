'use strict';
const fs = require('node:fs'), path = require('node:path');
const report = JSON.parse(fs.readFileSync(process.argv[2] || path.join(__dirname, '../docs/web-build-report.json')));
if (!report.quotaConfirmed) {
  console.error('Confirm the Azure single-environment quota, then set the SWA_QUOTA_MB repository variable. No subscription changes are made by this workflow.');
  process.exitCode = 1;
} else if (report.overBudgetBytes > 0) {
  console.error('Publish blocked: ' + (report.totalBytes / 1e6).toFixed(2) + ' MB exceeds the 90% budget by ' + (report.overBudgetBytes / 1e6).toFixed(2) + ' MB. All model details are preserved.');
  process.exitCode = 1;
} else console.log('Publish size verified: ' + (report.totalBytes / 1e6).toFixed(2) + ' MB');
