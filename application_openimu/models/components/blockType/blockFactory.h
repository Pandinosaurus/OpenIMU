#ifndef BLOCKFACTORY_H
#define BLOCKFACTORY_H
#include "../block.h"
#include "string"


class BlockFactory
{
public:
    BlockFactory();
    Block* createBlockType(std::string blockType);
};

#endif // BLOCKFACTORY_H
