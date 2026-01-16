const {onRequest} = require("firebase-functions/v2/https");
const logger = require("firebase-functions/logger");

exports.helloWorld = onRequest({cors: true}, (request, response) => {
  const name = request.query.name || "Visitante";
  const serverTime = new Date().toISOString();

  logger.info(`Saludo enviado a: ${name}`, {structuredData: true});

  response.json({
    message: `Hola ${name}, bienvenido a la infraestructura de dblkl.com`,
    time: serverTime,
    status: "Cloud Function ejecutada con éxito",
  });
});
