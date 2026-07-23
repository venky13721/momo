// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "TranscribeCLI",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/FluidInference/FluidAudio.git", branch: "main")
    ],
    targets: [
        .executableTarget(
            name: "TranscribeCLI",
            dependencies: [.product(name: "FluidAudio", package: "FluidAudio")]
        )
    ]
)
