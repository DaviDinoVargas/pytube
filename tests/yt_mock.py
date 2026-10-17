"""Simulação local da API do player do YouTube (YT.Player), para testar a ponte sem rede."""

MOCK_API = r"""
window.YT = { Player: function (id, opts) {
  var t = 0, dur = 212, state = -1, q = 'hd720', rate = 1, vol = 100, muted = false, timer = null, self = this;
  window.__mock = this;
  this.options = opts;
  setTimeout(function () { opts.events.onReady({}); }, 20);
  this.playVideo = function () {
    state = 1; opts.events.onStateChange({data: 1});
    if (!timer) timer = setInterval(function () { if (state == 1) t += 0.5 * rate; if (t >= dur) { state = 0; opts.events.onStateChange({data: 0}); } }, 500);
  };
  this.pauseVideo = function () { state = 2; opts.events.onStateChange({data: 2}); };
  this.seekTo = function (s) { t = s; };
  this.getCurrentTime = function () { return t; };
  this.getDuration = function () { return dur; };
  this.getPlaybackQuality = function () { return q; };
  this.getAvailableQualityLevels = function () { return ['hd1080', 'hd720', 'large', 'medium', 'auto']; };
  this.setPlaybackQualityRange = function (a, b) { self.range = [a, b]; };
  this.setPlaybackQuality = function (x) { q = x === 'default' ? 'hd720' : x; opts.events.onPlaybackQualityChange({data: q}); };
  this.getVolume = function () { return vol; };
  this.setVolume = function (v) { vol = v; };
  this.isMuted = function () { return muted; };
  this.mute = function () { muted = true; };
  this.unMute = function () { muted = false; };
  this.getPlaybackRate = function () { return rate; };
  this.setPlaybackRate = function (r) { rate = r; opts.events.onPlaybackRateChange({data: r}); };
  this.getPlayerState = function () { return state; };
  this.fail = function (code) { opts.events.onError({data: code}); };
}};
setTimeout(function () { onYouTubeIframeAPIReady(); }, 0);
"""
