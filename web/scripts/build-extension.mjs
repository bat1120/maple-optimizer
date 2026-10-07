// extension/generated/run.js 를 web/src/scouter.js(북마크와 같은 교체·채우기 코드)에서 만든다: npm run ext
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { extensionRunModule } from "../src/scouter.js";

const out = fileURLToPath(new URL("../../extension/generated/run.js", import.meta.url));
writeFileSync(out, extensionRunModule(), "utf8");
console.log("wrote", out);
