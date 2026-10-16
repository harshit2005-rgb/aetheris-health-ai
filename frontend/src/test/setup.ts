import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'

/**
 * How long `findBy*` and `waitFor` wait before failing. The default of one
 * second is too tight on a busy CI runner, where a refetch and a re-render can
 * take longer, and tests failed at random ("Page 2 of 3" not found in
 * DoctorsPage.inactive). They still return the moment the element appears, so
 * a passing run is no slower; only a genuine failure takes longer to report.
 */
configure({ asyncUtilTimeout: 3000 })

/**
 * jsdom implements neither the Pointer Capture API nor `scrollIntoView`, both
 * of which Radix calls when a `Select` opens. Without these stubs any test that
 * opens a dropdown dies with `target.hasPointerCapture is not a function`, and
 * the failure looks like a bug in the component rather than a gap in the DOM
 * implementation. Stubbed here once rather than in each test file.
 */
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false
  Element.prototype.setPointerCapture = () => {}
  Element.prototype.releasePointerCapture = () => {}
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// Radix `Checkbox` measures itself with a ResizeObserver, which jsdom lacks.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
