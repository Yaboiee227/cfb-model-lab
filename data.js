(() => {
  const parts = [];
  for (let i = 0; i < 6; i += 1) {
    const name = `snapshot_chunks/data_${String(i).padStart(2, "0")}.part`;
    const xhr = new XMLHttpRequest();
    xhr.open("GET", name, false);
    xhr.send(null);
    if (xhr.status < 200 || xhr.status >= 300) {
      throw new Error(`Unable to load ${name}: HTTP ${xhr.status}`);
    }
    parts.push(xhr.responseText);
  }
  (0, eval)(parts.join(""));
})();
