/*
 * trim_heartbeat.scd
 * Run once to extract a single heartbeat (systole + diastole).
 * Output: whale_heart_wav/heartbeat_single.aif
 *
 * Cmd+A → Cmd+Return
 */
(
// All vars at top of outer block — SC rule
var root, inPath, outPath;

root    = thisProcess.nowExecutingPath.dirname +/+ "..";
inPath  = root +/+ "whale_heart_wav/zapsplat_animals_bluewhale_heartbeat_loop_26507.aif";
outPath = root +/+ "whale_heart_wav/heartbeat_single.aif";

Buffer.read(s, inPath, action: { |buf|
    // All vars at top of this block too
    var totalFrames, sr, totalSec, numBeats, oneBeatFrames, oneBeatSec;

    totalFrames   = buf.numFrames;
    sr            = buf.sampleRate;
    totalSec      = buf.duration;
    numBeats      = 6;   // adjust if your file has more or fewer beats
    oneBeatFrames = (totalFrames / numBeats).asInteger;
    oneBeatSec    = oneBeatFrames / sr;

    "Loaded: % sec  % frames  % ch".format(
        totalSec.round(0.001), totalFrames, buf.numChannels
    ).postln;
    "One beat: % frames  (% sec)".format(
        oneBeatFrames, oneBeatSec.round(0.001)
    ).postln;
    "Writing: %".format(outPath).postln;

    buf.write(outPath, "aif", "int24", oneBeatFrames, 0);

    { "Done — restart sclang to use heartbeat_single.aif".postln }.defer(1.0);
});
)
