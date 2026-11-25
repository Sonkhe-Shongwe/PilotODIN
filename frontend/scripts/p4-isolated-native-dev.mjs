// C5: executable native frontdoor is frozen irrespective of historical consent env.
// Pure native-dev-plan.mjs remains available for source-only tests.
// Previous executable route retained at eb216a634ec1442579a89651c39f809ccf997cce:frontend/scripts/p4-isolated-native-dev.mjs.
console.error("STOP: Native compilation is frozen pending separate explicit owner approval and reviewed exact build inputs.");
process.exit(2);
