import * as grpc from '@grpc/grpc-js';
import * as depi from './src/pbs/depi_pb';
import { DepiClient } from './src/pbs/depi_grpc_pb';
import { addAsyncMethods } from './src/pbs/addAsyncMethods';
import depiUtils, { DepiSession } from './src/depiUtils';
import {
    ResourcePattern,
    Resource,
    ResourceRef,
    ResourceGroupRef,
    ResourceGroup,
    ResourceLinkRef,
    ResourceLink,
    LinkPattern,
    ResourceChange,
    ChangeType,
} from './src/@types/depi';

export {
    grpc,
    depi,
    DepiClient,
    addAsyncMethods,
    depiUtils,
    DepiSession,
    ResourcePattern,
    Resource,
    ResourceRef,
    ResourceGroupRef,
    ResourceGroup,
    ResourceLinkRef,
    ResourceLink,
    LinkPattern,
    ResourceChange,
    ChangeType,
};