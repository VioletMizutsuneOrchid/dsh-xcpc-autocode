/**
 * DeepSeek Harness bundle entry for AutoCode.
 *
 * A bundle's `cordis.patch.yml` can only reference packages by name, and its
 * `config` values are written before the package is installed, so an absolute
 * path cannot be hardcoded there. Instead this module publishes the paths as a
 * Cordis service and the patch reads them back with `!!js ctx.autocodePaths.*`.
 *
 * The paths follow `import.meta.url`, so they stay correct for `dsh plugin add`
 * from a local checkout, from a git source, or from the npm registry.
 */
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { Service } from '@deepseek-ai/cordis'

/** `<packageRoot>/dsh/paths.mjs` -> `<packageRoot>`. */
const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)))

export default class AutocodePaths extends Service {
  constructor(ctx) {
    super(ctx, 'autocodePaths')
  }

  /**
   * Directory holding `pyproject.toml`, `uv.lock` and `src/autocode_mcp`, i.e.
   * the uv project the MCP server runs from. Override with
   * `AUTOCODE_PLUGIN_ROOT` when the sources live outside the installed package.
   */
  get project() {
    return process.env.AUTOCODE_PLUGIN_ROOT || packageRoot
  }

  /** Executable the MCP client spawns. Override with `AUTOCODE_MCP_COMMAND`. */
  get mcpCommand() {
    return process.env.AUTOCODE_MCP_COMMAND || 'uv'
  }

  /** Arguments that start the AutoCode MCP server from the bundled uv project. */
  get mcpArgs() {
    return ['run', '--project', this.project, 'autocode-mcp']
  }

  /** Bundled skills root (`<packageRoot>/skills`). */
  get skills() {
    return join(packageRoot, 'skills')
  }

  /** `customSkillDirs` value for the `dsh-skill-filesystem` provider row. */
  get skillDirs() {
    return [this.skills]
  }
}
