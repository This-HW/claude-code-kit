# db-architect Skill

Database architecture design specialist that creates robust, scalable, and performant database schemas.

## Usage

```bash
# Basic usage (auto-detect from context)
/db-architect "Design a schema for an e-commerce platform"

# With specific requirements
/db-architect "Design a multi-tenant SaaS database schema with user isolation"

# Schema migration
/db-architect "Analyze and improve existing schema at schema.sql"
```

## What It Does

### 1. Requirements Analysis

- Identifies entities and relationships
- Documents business rules
- Analyzes access patterns
- Estimates data volumes

### 2. ERD Design

- Creates entity-relationship diagrams
- Defines primary and foreign keys
- Specifies data types and constraints
- Documents relationships (1:1, 1:N, N:M)

### 3. Normalization

- Applies 3NF normalization by default
- Checks for normal form violations
- Recommends denormalization when justified
- Balances integrity vs. performance

### 4. Indexing Strategy

- Indexes WHERE/JOIN/ORDER BY columns
- Creates composite indexes strategically
- Implements partial indexes (PostgreSQL)
- Identifies and removes unused indexes

### 5. Performance Optimization

- Designs for common query patterns
- Implements partitioning for large tables
- Plans denormalization strategies
- Provides scalability recommendations

### 6. Schema Evolution

- Creates versioned migrations
- Ensures backward compatibility
- Supports zero-downtime deployments
- Documents migration strategy

## Outputs

1. **ERD Document** (`docs/schema/erd.md`)
   - Entity definitions
   - Relationship diagrams
   - Constraint specifications
   - Index rationale

2. **SQL Schema** (`schema.sql`)
   - Table creation statements
   - Index definitions
   - Foreign key constraints
   - CHECK constraints

3. **Performance Notes** (`docs/schema/performance.md`)
   - Query pattern analysis
   - Bottleneck mitigation
   - Scalability plan
   - Monitoring recommendations

## Best Practices Applied

- ✅ Surrogate keys (auto-increment/UUID)
- ✅ 3NF normalization by default
- ✅ Database-level referential integrity
- ✅ Smallest data types that fit
- ✅ Strategic indexing
- ✅ DECIMAL for currency (not FLOAT)
- ✅ Versioned migrations

## Integration

Works seamlessly with:

- **data-modeler**: Generates ORM entities from schema
- **migrate-data**: Executes migration scripts
- **optimize-queries**: Tunes query performance
- **postgres MCP**: Explores existing schemas

## Examples

### E-commerce Schema

```bash
/db-architect "E-commerce schema with users, products, orders, and reviews"
```

Produces:

- 5 normalized tables
- 8 strategic indexes
- Foreign key constraints
- Performance optimizations

### Multi-tenant SaaS

```bash
/db-architect "Multi-tenant SaaS with tenant isolation via tenant_id column"
```

Produces:

- Tenant isolation strategy
- Row-level security policies
- Composite indexes on (tenant_id, ...)
- Query optimization guidelines

## Requirements

- PostgreSQL, MySQL, or SQLite
- postgres MCP (optional, for schema exploration)
- Migration tool (Prisma, TypeORM, Alembic, etc.)

## Configuration

The skill automatically adapts to your:

- Database engine (PostgreSQL, MySQL, SQLite)
- Project structure
- Existing conventions

## Tips

1. **Be specific about requirements**
   - Describe data access patterns
   - Mention expected data volumes
   - Clarify relationships clearly

2. **Use postgres MCP for existing schemas**
   - Start SSH tunnel: `./scripts/db-tunnel.sh start`
   - Skill will analyze existing structure

3. **Review normalization decisions**
   - Skill defaults to 3NF
   - Ask about denormalization trade-offs if needed

4. **Check index strategy**
   - Review suggested indexes
   - Add missing query patterns if any

## Related Skills

- `/data-modeler` - Convert schema to ORM entities
- `/migrate-data` - Execute migrations
- `/optimize-queries` - Tune query performance
- `/design-database` - (Agent) Alternative entry point

## Version

- **Version**: 1.0.0
- **Model**: Opus (strategic/analytical tasks)
- **Domain**: data-engineering
