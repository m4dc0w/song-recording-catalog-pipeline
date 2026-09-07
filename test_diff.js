const fs = require('fs');
const Diff = require('diff');

const localText = fs.readFileSync('server.js', 'utf-8');
const remoteText = "";

const patch = Diff.createTwoFilesPatch(
  'server.js', 
  'server.js', 
  remoteText, 
  localText, 
  '', 
  ''
);

console.log(patch);
