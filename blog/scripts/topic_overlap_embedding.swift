import Foundation
import NaturalLanguage

guard let model = NLEmbedding.sentenceEmbedding(for: .english) else {
    fputs("English sentence embedding is unavailable on this Mac\n", stderr)
    exit(2)
}

let input = FileHandle.standardInput.readDataToEndOfFile()
guard let texts = try JSONSerialization.jsonObject(with: input) as? [String] else {
    fputs("Expected a JSON array of strings\n", stderr)
    exit(2)
}

let vectors = texts.map { text -> [Double] in
    model.vector(for: text) ?? Array(repeating: 0.0, count: model.dimension)
}
let output = try JSONSerialization.data(withJSONObject: vectors)
FileHandle.standardOutput.write(output)
