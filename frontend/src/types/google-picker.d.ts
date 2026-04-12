/**
 * google-picker.d.ts — Ambient type declarations for the Google Picker API (STORY-006-05).
 *
 * The Google Picker API is loaded dynamically via `gapi.load('picker', callback)`
 * after the Google API client script (`https://apis.google.com/js/api.js`) is
 * injected into the page. This file provides TypeScript types for the globals
 * that the script exposes, preventing `ts(7017)` errors in the Picker integration.
 *
 * Only the subset of the API used by WorkspaceDetailPage is declared here.
 * Extend as needed when new Picker views or features are added.
 *
 * Reference: https://developers.google.com/drive/picker/reference
 */

declare namespace google.picker {
  /**
   * Builder class for constructing a Google Drive Picker widget.
   * Chain methods to configure OAuth token, developer key, views, and callbacks.
   */
  class PickerBuilder {
    /** Sets the OAuth access token scoped to the connected Google account. */
    setOAuthToken(token: string): PickerBuilder;
    /** Sets the Google Cloud API key that controls Picker API quota. */
    setDeveloperKey(key: string): PickerBuilder;
    /** Adds a view to the Picker (e.g. all Drive documents). */
    addView(view: ViewId): PickerBuilder;
    /** Registers a callback invoked when the user picks a file or cancels. */
    setCallback(callback: (data: CallbackData) => void): PickerBuilder;
    /** Finalises the configuration and returns a Picker instance. */
    build(): Picker;
  }

  /** A configured Google Picker widget instance. */
  interface Picker {
    /** Shows or hides the Picker dialog. Pass `true` to open. */
    setVisible(visible: boolean): void;
  }

  /**
   * Callback data passed to the function registered via `setCallback`.
   * Always present; `docs` is only populated when `action === Action.PICKED`.
   */
  interface CallbackData {
    /** The action that triggered this callback. */
    action: string;
    /** Files selected by the user. Only present when `action === 'picked'`. */
    docs?: Array<{
      /** Google Drive file ID. */
      id: string;
      /** File name in Google Drive. */
      name: string;
      /** Direct URL to the file in Google Drive. */
      url: string;
      /** MIME type of the selected file. */
      mimeType: string;
    }>;
  }

  /** Action values used in `CallbackData.action`. */
  enum Action {
    /** The user selected one or more files. */
    PICKED = 'picked',
    /** The user cancelled without selecting a file. */
    CANCEL = 'cancel',
  }

  /** Picker view identifiers. */
  enum ViewId {
    /** Shows all files in the user's Google Drive. */
    DOCS = 'DOCS',
  }
}

/**
 * Google API Client library global, injected by
 * `<script src="https://apis.google.com/js/api.js">`.
 *
 * Provides `gapi.load(api, callback)` for loading specific Google API modules
 * (such as the Google Picker) on demand.
 */
declare const gapi: {
  /**
   * Loads a Google API module by name and invokes the callback when ready.
   *
   * @param api      - API module name, e.g. `'picker'`.
   * @param callback - Called once the module is loaded and available.
   */
  load(api: string, callback: () => void): void;
};
