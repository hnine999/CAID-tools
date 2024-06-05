npm --prefix ./blackboard-graph install
npm --prefix ./blackboard-graph run build
npm --prefix ./vscode-depi install
npm --prefix ./vscode-depi run compile
(cd vscode-depi && vsce package)