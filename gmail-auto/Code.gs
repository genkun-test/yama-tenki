// Gmail に届いた YAMAP の通知から、いちばん新しい登山計画のURLだけを返す
function doGet() {
  var threads = GmailApp.search('from:noreply@yamap.co.jp newer_than:90d', 0, 10);
  for (var i = 0; i < threads.length; i++) {
    var msgs = threads[i].getMessages();
    for (var j = msgs.length - 1; j >= 0; j--) {
      var m = msgs[j].getPlainBody().match(/https:\/\/yamap\.com\/plans\/code\/[A-Za-z0-9_-]+/);
      if (m) return ContentService.createTextOutput(m[0]);
    }
  }
  return ContentService.createTextOutput('');
}
