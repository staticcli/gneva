const path = require("path");

module.exports = {
    mode: "production",
    entry: "./index.js",
    output: {
        filename: "acs_calling_bundle.js",
        path: path.resolve(__dirname, "dist"),
    },
    resolve: {
        extensions: [".js"],
    },
};
