var VERSION_URL = 'https://sawtooth.hyperledger.org/docs/versions.json';
var versionRequest = new XMLHttpRequest();
var versionSwitcher = document.getElementById('version_switcher');

versionSwitcher.onchange = function() {
  if (this.value) {
    window.location.assign(this.value);
  }
};

versionRequest.onreadystatechange = function() {
  if (!versionSwitcher.length && versionRequest.responseText) {
    var versions = JSON.parse(versionRequest.responseText);
    versions.forEach(function(versionTuple) {
      var option = document.createElement('option');
      option.innerText = versionTuple[0];
      option.value = versionTuple[1];
      versionSwitcher.appendChild(option);
      if (window.location.href === option.value) {
        option.selected = true;
      }
    });
  }
};

versionRequest.open('GET', VERSION_URL, true);
versionRequest.send(null);
