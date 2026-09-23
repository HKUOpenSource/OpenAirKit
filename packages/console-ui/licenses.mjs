import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";

// Include notices for packages whose modules are included in the browser build.
export function frontendLicenses() {
  return {
    name: "console-ui-licenses",
    generateBundle() {
      const packages = new Map();
      for (const id of this.getModuleIds()) {
        if (!id.includes("/node_modules/")) continue;
        let directory = dirname(id.split("?")[0]);
        while (directory.includes("/node_modules/")) {
          const manifest = join(directory, "package.json");
          if (existsSync(manifest)) {
            const metadata = JSON.parse(readFileSync(manifest, "utf8"));
            if (metadata.name && metadata.version) {
              packages.set(metadata.name, { directory, metadata });
              break;
            }
          }
          directory = dirname(directory);
        }
      }
      const notices = [];
      for (const [name, { directory, metadata }] of [...packages].sort()) {
        let files = readdirSync(directory).filter((file) =>
          /^(license|copying|notice)(\.|$)/i.test(file),
        );
        // These pinned npm tarballs omit their upstream license files.
        const fallback = {
          "@astryxdesign/core@0.6.2-canary.d72e4d6": "Astryx.txt",
          "@stylexjs/stylex@0.19.0": "StyleX.txt",
        }[`${name}@${metadata.version}`];
        if (!files.length && fallback) {
          notices.push(
            `${name}@${metadata.version} (${metadata.license})\n\n` +
              readFileSync(
                new URL(`./licenses/${fallback}`, import.meta.url),
                "utf8",
              ),
          );
          continue;
        }
        if (!files.length)
          this.error(`Missing license text for bundled dependency ${name}`);
        notices.push(
          `${name}@${metadata.version} (${metadata.license || "see license"})\n\n` +
            files
              .map((file) => readFileSync(join(directory, file), "utf8"))
              .join("\n\n"),
        );
      }
      this.emitFile({
        type: "asset",
        fileName: "THIRD_PARTY_NOTICES.txt",
        source: notices.join("\n\n---\n\n"),
      });
    },
  };
}
