// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
//
import { config } from 'dotenv';
const ENV_FILE = path.join(__dirname, '..', '.env');
config({ path: ENV_FILE });

import * as restify from 'restify';

import { INodeSocket } from 'botframework-streaming';

// Import required bot services.
// See https://aka.ms/bot-services to learn more about the different parts of a bot.
import { 
    CloudAdapter,
    ConfigurationServiceClientCredentialFactory,
    createBotFrameworkAuthenticationFromConfiguration
} from 'botbuilder';

// This bot's main dialog.
import { Bot } from './bot';

// Enable debug
import { setLogLevel } from "@azure/logger";
setLogLevel('verbose');

// Create HTTP server.
const server = restify.createServer();
server.use(restify.plugins.bodyParser());
server.listen(process.env.bot_port || process.env.BOT_PORT || 3978, () => {
    console.log(`\n${server.name} listening to ${server.url}`);
    console.log('\nGet Bot Framework Emulator: https://aka.ms/botframework-emulator');
    console.log('\nTo talk to your bot, open the emulator select "Open Bot"');
});

// Accept both naming schemes. The SDK's own names (MicrosoftAppId,
// MicrosoftAppPassword, MicrosoftAppTenantId) win, but README.md has always
// documented AppId / AppPassword / AuthTenantID, and deployments were written
// against those -- the GCP Marketplace chart injected AppPassword, which nothing
// here read, so the Teams channel could not start: with MicrosoftAppType
// SingleTenant the SDK asserts "MicrosoftAppPassword is required" and the
// process exits, leaving nothing on port 3978.
//
// An empty string is falsy, so an unset-or-blank primary falls through to the
// alias and a deployment setting either name works.
const credentialsFactory = new ConfigurationServiceClientCredentialFactory({
    MicrosoftAppId: process.env.MicrosoftAppId || process.env.AppId,
    MicrosoftAppPassword: process.env.MicrosoftAppPassword || process.env.AppPassword,
    MicrosoftAppType: process.env.MicrosoftAppType,
    MicrosoftAppTenantId: process.env.MicrosoftAppTenantId || process.env.AuthTenantID
});

const botFrameworkAuthentication = createBotFrameworkAuthenticationFromConfiguration(null, credentialsFactory);

// Create adapter.
// See https://aka.ms/about-bot-adapter to learn more about how bots work.
const adapter = new CloudAdapter(botFrameworkAuthentication);

// Catch-all for errors.
const onTurnErrorHandler = async (context, error) => {
    // This check writes out errors to console log .vs. app insights.
    // NOTE: In production environment, you should consider logging this to Azure
    //       application insights.
    console.error(`\n [onTurnError] unhandled error: ${ error }`);

    // Send a trace activity, which will be displayed in Bot Framework Emulator
    await context.sendTraceActivity(
        'OnTurnError Trace',
        `${ error }`,
        'https://www.botframework.com/schemas/error',
        'TurnError'
    );

    // TODO Enable debug through app config
    // Send a message to the user
    await context.sendActivity('The bot encountered an error or bug. Please, try again later or contact the support.');
};

// Set the onTurnError for the singleton CloudAdapter.
adapter.onTurnError = onTurnErrorHandler;

// Create the main dialog.
const nlBot = new Bot({
    debug: process.env.DEBUG === 'true',
    nlApiUrl: process.env.nlapiurl ?? 'http://localhost:8000/nlsql-analyzer'
});

// Never log process.env itself: it carries DbPassword, ApiToken and AppPassword,
// which ECS injects from Secrets Manager. supervisord forwards stdout to the
// awslogs driver, so dumping it writes every credential into CloudWatch Logs in
// plaintext, readable by anyone with log access in the buyer's account. Log the
// names only - that keeps the "is my variable set?" debugging value without the
// leak.
console.log('env keys:', Object.keys(process.env).sort().join(', '));

// Listen for incoming requests.
server.post(
  '/api/messages',
  (req: restify.Request, res: restify.Response, next: restify.Next) => {
    adapter
      .process(req, res, async (context) => {
        await nlBot.run(context);
      })
      .then(() => next())
      .catch((err) => {
        console.error('Error in bot adapter:', err);
        res.send(500, { error: 'Internal Server Error' });
        return next(err);
      });
  }
);


// Listen for Upgrade requests for Streaming.
server.on('upgrade', async (req, socket, head) => {
    // Create an adapter scoped to this WebSocket connection to allow storing session data.
    const streamingAdapter = new CloudAdapter(botFrameworkAuthentication);

    // Set onTurnError for the CloudAdapter created for each connection.
    streamingAdapter.onTurnError = onTurnErrorHandler;

    await streamingAdapter.process(req, socket as unknown as INodeSocket, head, (context) => nlBot.run(context));
});
