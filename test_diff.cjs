const fs = require('fs');
const Diff = require('diff'); // wait, I don't have diff installed in node_modules!

const localText = "hello\nworld";
const remoteText = "";

try {
  const patch = Diff.createTwoFilesPatch('a.txt', 'a.txt', remoteText, localText, '', '');
  console.log(patch);
} catch (e) {
  console.log(e);
}
