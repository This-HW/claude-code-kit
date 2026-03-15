# data-modeler Skill

Data modeling specialist that translates database schemas into ORM entities with proper relationships, constraints, and migrations.

## Usage

```bash
# From SQL schema
/data-modeler "Convert schema.sql to Prisma models"

# From ERD document
/data-modeler "Generate TypeORM entities from docs/schema/erd.md"

# With existing entities
/data-modeler "Add Product-Category many-to-many relationship to Prisma schema"
```

## What It Does

### 1. Schema Analysis

- Parses SQL schema (from db-architect)
- Extracts entities, columns, types
- Identifies relationships (foreign keys)
- Maps constraints to ORM syntax

### 2. Entity Definition

- Generates ORM-specific code
- Supports multiple ORMs:
  - **Prisma**: schema.prisma (declarative)
  - **TypeORM**: entities/\*.ts (decorators)
  - **SQLAlchemy**: models/\*.py (Python)
  - **Sequelize**: models/\*.js (Node.js)

### 3. Relationship Mapping

- **1:1** (One-to-One): User ↔ Profile
- **1:N** (One-to-Many): User → Orders
- **N:M** (Many-to-Many): Products ↔ Categories
- Explicit junction tables (recommended)

### 4. Constraint Mapping

- CHECK constraints
- UNIQUE constraints (single/composite)
- NOT NULL (via nullable)
- DEFAULT values
- Enum types

### 5. Migration Generation

- Auto-generates migration scripts
- Supports up/down migrations
- Version-controlled migrations
- Backward-compatible changes

### 6. Type Safety

- Generates TypeScript types (Prisma/TypeORM)
- Python type hints (SQLAlchemy)
- Auto-completion in IDE
- Compile-time error checking

## Outputs

1. **ORM Entities**
   - Prisma: `schema.prisma`
   - TypeORM: `entities/*.ts`
   - SQLAlchemy: `models/*.py`

2. **Migration Scripts**
   - `migrations/001_initial.sql`
   - `migrations/002_add_profile.sql`
   - Migration guide

3. **Usage Examples**
   - CRUD operations
   - Relationship queries
   - Type-safe examples

4. **Type Definitions**
   - Auto-generated types
   - Relation types
   - Input/output types

## ORM Support

### Prisma (TypeScript)

**Strengths:**

- Declarative schema language
- Type-safe client generation
- Automatic migrations
- Best-in-class DX

**Example:**

```prisma
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  orders    Order[]
}
```

### TypeORM (TypeScript)

**Strengths:**

- Decorator-based syntax
- Active Record / Data Mapper
- Wide database support
- Flexible migrations

**Example:**

```typescript
@Entity()
class User {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ unique: true })
  email: string;

  @OneToMany(() => Order, (order) => order.user)
  orders: Order[];
}
```

### SQLAlchemy (Python)

**Strengths:**

- Pythonic API
- Powerful query builder
- Hybrid approach
- Production-proven

**Example:**

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    orders: Mapped[List["Order"]] = relationship()
```

## Integration

Works seamlessly with:

- **db-architect**: Receives SQL schema as input
- **migrate-data**: Executes generated migrations
- **optimize-queries**: Optimizes ORM queries
- **Context7 MCP**: Fetches ORM documentation

## Examples

### E-commerce Entities (Prisma)

```bash
/data-modeler "Generate Prisma schema from docs/schema/erd.md"
```

Produces:

- `schema.prisma` with 5 models
- Relationships configured
- Indexes declared
- Migrations ready

### Add Many-to-Many (TypeORM)

```bash
/data-modeler "Add Product-Category many-to-many with junction table"
```

Produces:

- Updated Product entity
- Updated Category entity
- ProductCategory junction entity
- Migration script

## Requirements

- Node.js 18+ (Prisma/TypeORM)
- Python 3.10+ (SQLAlchemy)
- ORM package installed
- Migration tool configured

## Configuration

The skill automatically:

- Detects ORM from package.json / requirements.txt
- Follows project conventions
- Uses existing naming patterns
- Matches code style

## Tips

1. **Specify ORM explicitly if unclear**

   ```bash
   /data-modeler "Use Prisma to model..."
   ```

2. **Use Context7 for ORM docs**
   - Skill automatically fetches latest syntax
   - Ensures compatibility with your version

3. **Review generated migrations**
   - Check up/down logic
   - Test on development database
   - Review SQL output

4. **Leverage type safety**
   - Use generated types in code
   - Enable strict TypeScript
   - Run type checks before commit

## Common Patterns

### Soft Delete

```typescript
@DeleteDateColumn()
deletedAt: Date;
```

### Timestamps

```typescript
@CreateDateColumn()
createdAt: Date;

@UpdateDateColumn()
updatedAt: Date;
```

### Optimistic Locking

```typescript
@VersionColumn()
version: number;
```

### Enums

```typescript
enum Status {
  PENDING = 'pending',
  ACTIVE = 'active',
  ARCHIVED = 'archived'
}

@Column({ type: 'enum', enum: Status })
status: Status;
```

## Schema Evolution

### Safe Changes (No Downtime)

- ✅ Add nullable column
- ✅ Add new table
- ✅ Add index
- ✅ Increase VARCHAR size

### Risky Changes (Coordination Required)

- ⚠️ Add NOT NULL column → Use default + backfill
- ⚠️ Rename column → 3-step migration
- ⚠️ Change data type → Careful casting
- ⚠️ Drop column/table → Check dependencies

### Zero-Downtime Pattern

```
1. Expand (add new)
2. Migrate (copy data)
3. Update (change code)
4. Contract (remove old)
```

## Related Skills

- `/db-architect` - Design SQL schema first
- `/migrate-data` - Execute migrations
- `/optimize-queries` - Query performance
- `/design-database` - (Agent) Alternative entry point

## Version

- **Version**: 1.0.0
- **Model**: Sonnet (implementation tasks)
- **Domain**: data-engineering
