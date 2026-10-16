import Foundation
import Vision
import AppKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(url: url)
do {
    try handler.perform([request])
    for result in request.results ?? [] {
        if let text = result.topCandidates(1).first { print(text.string) }
    }
} catch { fputs(error.localizedDescription, stderr); exit(1) }
