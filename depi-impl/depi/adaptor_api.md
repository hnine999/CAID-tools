# Depi APIs

## Common Data Structures

### ResourceGroup

```
  Name: String
  URL: String
  Version: String
  Resources: [Resource]
```

### Resource

```
  Name: String
  URL: String
```

## API For Tool Adaptors

The API For Tool Adaptors defines the interactions a tool adaptor
has to make with the DEPI

### Login

The Tool Adaptor must log in to the DEPI on behalf of a user. This provides some
basic security for the DEPI, and also allows it to track which users made which
changes.

Request:

```
User: String
Password: String
Project: String
```

Response:

```
OK: Boolean
Message: String
CallbackToken: String
```

### RegisterCallback

The RegisterCallback request causes the HTTPS connection to be converted to
a WebSocket stream that will then send asynchronous messages.

Request:

```
CallbackToken: String
```

### ResourcesUpdated

The ResourcesUpdated request notifies the DEPI that resources in the
tool have been updated.

Request:

```
ToolVersion: String
```

### WatchResourceGroup

The WatchResourceGroup request notifies the DEPI that the tool adaptor
wants to be notified when changes happen to a particular resource group.

Request:

```
ResourceGroup: URL
```

### UnwatchResourceGroup

The UnwatchResourceGroup request notifies the DEPI that the tool adaptor
no longer wants to be notified when changes happen to a particular resource
group.

Request:

```
ResourceGroup: URL
```

## Tool Adaptor Callback API

The Callback API defines the messages that the DEPI can send as
callback messages. The DEPI callback messages are one-way asynchronous
notifications.

## API For Blackboard

### Login

Request:

```
User: String
Password: String
Project: String
```

Response:

```
OK: Boolean
Message: String
```

### Add Resources To Blackboard

Request:

```
Resources: [Resource]
```

Response:

```
OK: Boolean
Message: String
```

### Link Blackboard Resources

Request:

```
ResourceURLS: [String]
```

Response:

```
OK: Boolean
Message: String
```

### Save Blackboard

Request:

Response:

```
OK: Boolean
Message: String
```
