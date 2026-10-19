// A Whale's Heart — the prototype's canvas colours per look (web build).
// tools/build_web.py wraps every colour literal in the prototype's drawing code as PAL('<dark colour>').
// Dark returns the literal itself, so the dark look is the prototype exactly as it was.
// Light and paper map each dark colour to its counterpart: same entity, same hue family
// (darkstyle rule 2), stepped for a light ground; receding things move toward the ground (rule 4).
(function () {
  const DEPTH = { light: "0,115,158", paper: "47,93,124" };      // depth / the track: cyan → teal-blue / ink-blue
  const HEART = { light: "163,90,0", paper: "156,103,16" };      // heartbeat: amber → deep amber / ochre
  const LUNGE = { light: "194,24,91", paper: "168,70,127" };     // feeding: pink → raspberry / rose
  const INK = { light: "45,58,92", paper: "51,32,58" };          // grid, axes: navy line → ground ink
  const TXT = { light: "70,80,122", paper: "94,74,90" };         // canvas labels
  const look = (l) => ({
    "#041628": l === "light" ? "#fbfcfe" : "#f9f1e9",           // depth panel
    "#020c18": l === "light" ? "#f4f6fa" : "#f3e5da",           // plot ground, map gradient top
    "#041a2e": l === "light" ? "#e8ecf3" : "#eadbd0",           // map gradient bottom
    "rgba(11,37,64,1)": `rgba(${INK[l]},.35)`,
    "rgba(11,37,64,.9)": `rgba(${INK[l]},.15)`,
    "rgba(11,37,64,.8)": `rgba(${INK[l]},.18)`,
    "rgba(11,37,64,.6)": `rgba(${INK[l]},.12)`,
    "rgba(61,106,138,.7)": `rgba(${TXT[l]},.9)`,
    "rgba(90,138,170,.55)": `rgba(${TXT[l]},.75)`,
    "rgba(200,200,255,.5)": `rgba(${TXT[l]},.5)`,
    "rgba(255,255,255,.22)": `rgba(${INK[l]},.3)`,              // playhead
    "#fff": `rgb(${DEPTH[l]})`,                                  // dot cores: white would vanish
    "rgba(0,212,255,.04)": `rgba(${DEPTH[l]},.04)`,             // depth fill, surface → …
    "rgba(0,150,220,.15)": `rgba(${DEPTH[l]},.12)`,
    "rgba(0,60,160,.4)": `rgba(${DEPTH[l]},.3)`,                //   … deep: darker on a light ground
    "rgba(0,212,255,.9)": `rgba(${DEPTH[l]},.95)`,              // depth line
    "rgba(0,212,255,.8)": `rgba(${DEPTH[l]},.85)`,              // track travelled
    "rgba(0,212,255,.5)": `rgba(${DEPTH[l]},.4)`,
    "rgba(0,212,255,.4)": `rgba(${DEPTH[l]},.35)`,
    "rgba(0,212,255,0)": `rgba(${DEPTH[l]},0)`,
    "rgba(0,80,120,.4)": `rgba(${DEPTH[l]},.3)`,                // track ahead
    "rgba(255,170,44,.75)": `rgba(${HEART[l]},.85)`,            // heart-rate line
    "#ffaa2c": `rgb(${HEART[l]})`,
    "rgba(255,107,157,.9)": `rgba(${LUNGE[l]},.9)`,
    "rgba(255,107,157,.55)": `rgba(${LUNGE[l]},.75)`,
    "rgba(255,107,157,.07)": `rgba(${LUNGE[l]},.09)`,
    "#ff6b9d": `rgb(${LUNGE[l]})`,
  });
  const TABLE = { light: look("light"), paper: look("paper") };
  window.WHALE_PAL_KEYS = Object.keys(TABLE.light);             // the build checks it wraps exactly these
  window.PAL = function (c) {
    const t = TABLE[window.DarkStyle ? DarkStyle.get() : "dark"];
    return (t && t[c]) || c;
  };
})();
