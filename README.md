# Hi, I'm Sanhuo 👋

Student at Beijing Institute of Technology (BIT), building reliable AI agents and developer tools.

I focus on agent runtime correctness, observability, and reproducible evaluation. My recent upstream work spans Rust, TypeScript, and Python.

## Selected engineering contributions

- **[Goose — GenAI semantic-convention telemetry](https://github.com/aaif-goose/goose/pull/10700):** added standardized OpenTelemetry attributes to model and tool spans while preserving stable message IDs. **Merged.**
- **[Qwen Code — inline terminal image rendering](https://github.com/QwenLM/qwen-code/pull/8305):** renders assistant and tool PNGs through native Kitty/Ghostty placement or a `chafa` fallback while preserving stream order. **In review.**
- **[Gemini CLI — diff-aware `@` processing](https://github.com/google-gemini/gemini-cli/pull/28581):** prevents unified and combined diff hunk markers from triggering recursive workspace scans. **In review.**
- **[OpenHands — concurrent streaming message order](https://github.com/OpenHands/OpenHands/pull/16119):** keeps queued user messages correctly positioned across overlapping main-agent and planning-agent streams. **In review.**
- **[NanoClaw — legacy wiring migration](https://github.com/nanocoai/nanoclaw/pull/3145):** backfills missing channel destinations without overwriting existing names. **In review.**

## Open-source activity

<p align="center">
  <a href="https://github.com/search?q=is%3Apr+author%3Atlysanhuo+-user%3Atlysanhuo+is%3Amerged&type=pullrequests">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./assets/oss-contributions-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="./assets/oss-contributions-light.svg">
      <img alt="Merged open-source contributions by tlysanhuo" src="./assets/oss-contributions-light.svg" width="840">
    </picture>
  </a>
</p>
