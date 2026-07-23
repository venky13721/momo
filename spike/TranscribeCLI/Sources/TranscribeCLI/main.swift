// Throwaway Phase 0 spike: measure Parakeet v3 transcription latency via FluidAudio.
// Usage: swift run -c release TranscribeCLI <audio.wav>
// Prints model-load time, transcript, latency, and RTFx. See spike/README.md —
// if the FluidAudio API has drifted, fix up against its current README.

import AVFoundation
import FluidAudio
import Foundation

func loadSamples16kMono(_ url: URL) throws -> [Float] {
    let file = try AVAudioFile(forReading: url)
    let outFormat = AVAudioFormat(
        commonFormat: .pcmFormatFloat32, sampleRate: 16_000, channels: 1, interleaved: false)!
    let converter = AVAudioConverter(from: file.processingFormat, to: outFormat)!
    let inBuf = AVAudioPCMBuffer(
        pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length))!
    try file.read(into: inBuf)
    let ratio = outFormat.sampleRate / file.processingFormat.sampleRate
    let outBuf = AVAudioPCMBuffer(
        pcmFormat: outFormat,
        frameCapacity: AVAudioFrameCount(Double(file.length) * ratio) + 1024)!
    var consumed = false
    var convError: NSError?
    converter.convert(to: outBuf, error: &convError) { _, status in
        if consumed {
            status.pointee = .endOfStream
            return nil
        }
        consumed = true
        status.pointee = .haveData
        return inBuf
    }
    if let convError { throw convError }
    return Array(UnsafeBufferPointer(
        start: outBuf.floatChannelData![0], count: Int(outBuf.frameLength)))
}

guard CommandLine.arguments.count > 1 else {
    print("usage: TranscribeCLI <audio.wav>")
    exit(1)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])

let sem = DispatchSemaphore(value: 0)
Task {
    defer { sem.signal() }
    do {
        var t0 = Date()
        let models = try await AsrModels.downloadAndLoad()
        let manager = AsrManager(config: .default)
        try await manager.initialize(models: models)
        print(String(format: "model load: %.2fs", Date().timeIntervalSince(t0)))

        let samples = try loadSamples16kMono(url)
        let audioSec = Double(samples.count) / 16_000.0

        t0 = Date()
        let result = try await manager.transcribe(samples, source: .microphone)
        let dt = Date().timeIntervalSince(t0)

        print("---\n\(result.text)\n---")
        print(String(
            format: "latency: %.3fs  audio: %.1fs  RTFx: %.1f", dt, audioSec, audioSec / dt))
    } catch {
        print("error: \(error)")
        exit(1)
    }
}
sem.wait()
